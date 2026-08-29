#include "engine/sstable.hpp"
#include "util/crc32.hpp"

#include <fcntl.h>
#include <unistd.h>
#include <cassert>
#include <cstring>
#include <algorithm>
#include <ctime>

namespace mvdb {

static constexpr uint64_t SST_MAGIC = 0x4D565354424C4551ULL;

static void write_all(int fd, const void* buf, size_t len) {
    const uint8_t* p = (const uint8_t*)buf;
    while (len) {
        ssize_t n = ::write(fd, p, len);
        assert(n > 0);
        p += n;
        len -= n;
    }
}

void SSTable::build(const std::string& path,
                    const std::vector<std::pair<std::string, std::string>>& kvs) {

    int fd = ::open(path.c_str(), O_CREAT | O_TRUNC | O_WRONLY, 0644);
    assert(fd >= 0);

    std::vector<IndexEntry> index;

    for (const auto& kv : kvs) {
        uint64_t offset = ::lseek(fd, 0, SEEK_CUR);

        uint32_t key_len = kv.first.size();
        uint32_t val_len = kv.second.size();
        uint64_t expire_ts = 0;

        write_all(fd, &key_len, sizeof(key_len));
        write_all(fd, &val_len, sizeof(val_len));
        write_all(fd, &expire_ts, sizeof(expire_ts));
        write_all(fd, kv.first.data(), key_len);
        write_all(fd, kv.second.data(), val_len);

        uint32_t crc = crc32(
            0, key_len, val_len, expire_ts,
            kv.first.data(), key_len,
            kv.second.data(), val_len);

        write_all(fd, &crc, sizeof(crc));

        index.push_back({kv.first, offset});
    }

    uint64_t index_offset = ::lseek(fd, 0, SEEK_CUR);

    for (auto& e : index) {
        uint32_t len = e.key.size();
        write_all(fd, &len, sizeof(len));
        write_all(fd, e.key.data(), len);
        write_all(fd, &e.offset, sizeof(e.offset));
    }

    uint64_t index_size = ::lseek(fd, 0, SEEK_CUR) - index_offset;

    write_all(fd, &index_offset, sizeof(index_offset));
    write_all(fd, &index_size, sizeof(index_size));
    write_all(fd, &SST_MAGIC, sizeof(SST_MAGIC));

    ::close(fd);
}

SSTable::SSTable(const std::string& path) {
    fd_ = ::open(path.c_str(), O_RDONLY);
    assert(fd_ >= 0);

    ::lseek(fd_, -24, SEEK_END);
    uint64_t magic;
    ::read(fd_, &index_offset_, sizeof(index_offset_));
    ::read(fd_, &index_size_, sizeof(index_size_));
    ::read(fd_, &magic, sizeof(magic));

    assert(magic == SST_MAGIC);

    load_index();
}

SSTable::~SSTable() {
    ::close(fd_);
}

void SSTable::load_index() {
    ::lseek(fd_, index_offset_, SEEK_SET);

    uint64_t end = index_offset_ + index_size_;
    while ((uint64_t)::lseek(fd_, 0, SEEK_CUR) < end) {
        uint32_t len;
        ::read(fd_, &len, sizeof(len));
        std::string key(len, '\0');
        ::read(fd_, key.data(), len);
        uint64_t offset;
        ::read(fd_, &offset, sizeof(offset));
        index_.push_back({key, offset});
    }
}

bool SSTable::get(const char* key, uint32_t key_len,
                  std::string& value_out) {

    std::string k(key, key_len);

    auto it = std::lower_bound(
        index_.begin(), index_.end(), k,
        [](const IndexEntry& e, const std::string& v) {
            return e.key < v;
        });

    if (it == index_.end() || it->key != k)
        return false;

    ::lseek(fd_, it->offset, SEEK_SET);

    uint32_t kl, vl;
    uint64_t expire_ts;
    ::read(fd_, &kl, sizeof(kl));
    ::read(fd_, &vl, sizeof(vl));
    ::read(fd_, &expire_ts, sizeof(expire_ts));

    std::string key_buf(kl, '\0');
    std::string val_buf(vl, '\0');
    ::read(fd_, key_buf.data(), kl);
    ::read(fd_, val_buf.data(), vl);

    uint32_t crc_file;
    ::read(fd_, &crc_file, sizeof(crc_file));

    uint32_t crc_calc = crc32(
        0, kl, vl, expire_ts,
        key_buf.data(), kl,
        val_buf.data(), vl);

    if (crc_file != crc_calc)
        return false;

    value_out = val_buf;
    return true;
}

bool SSTable::read_record(uint64_t offset, std::string& key_out,
                          std::string& val_out, uint64_t& expire_ts_out) {
    ::lseek(fd_, offset, SEEK_SET);

    uint32_t kl, vl;
    uint64_t expire_ts;
    if (::read(fd_, &kl, sizeof(kl)) != sizeof(kl)) return false;
    if (::read(fd_, &vl, sizeof(vl)) != sizeof(vl)) return false;
    if (::read(fd_, &expire_ts, sizeof(expire_ts)) != sizeof(expire_ts)) return false;

    std::string key_buf(kl, '\0');
    std::string val_buf(vl, '\0');
    if (::read(fd_, key_buf.data(), kl) != (ssize_t)kl) return false;
    if (vl > 0 && ::read(fd_, val_buf.data(), vl) != (ssize_t)vl) return false;

    uint32_t crc_file;
    if (::read(fd_, &crc_file, sizeof(crc_file)) != sizeof(crc_file)) return false;

    uint32_t crc_calc = crc32(
        0, kl, vl, expire_ts,
        key_buf.data(), kl,
        val_buf.data(), vl);

    if (crc_file != crc_calc)
        return false;

    key_out = std::move(key_buf);
    val_out = std::move(val_buf);
    expire_ts_out = expire_ts;
    return true;
}

void SSTable::scan_prefix(const std::string& prefix,
                          std::vector<std::pair<std::string, std::string>>& results) {
    auto it = std::lower_bound(
        index_.begin(), index_.end(), prefix,
        [](const IndexEntry& e, const std::string& v) {
            return e.key < v;
        });

    uint64_t now = (uint64_t)std::time(nullptr);
    for (; it != index_.end(); ++it) {
        if (it->key.compare(0, prefix.size(), prefix) != 0)
            break;
        std::string k, v;
        uint64_t exp = 0;
        if (read_record(it->offset, k, v, exp)) {
            if (exp == 0 || exp >= now) {
                results.emplace_back(std::move(k), std::move(v));
            }
        }
    }
}

} // namespace mvdb
