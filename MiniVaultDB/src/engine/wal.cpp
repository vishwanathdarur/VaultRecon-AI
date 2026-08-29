#include "engine/wal.hpp"
#include "util/crc32.hpp"

#include <unistd.h>
#include <fcntl.h>
#include <cassert>
#include <cstring>
#include <ctime>

namespace mvdb {

WAL::WAL(const std::string& path) {
    fd_ = ::open(path.c_str(), O_CREAT | O_RDWR | O_APPEND, 0644);
    assert(fd_ >= 0);
}

WAL::~WAL() {
    if (fd_ >= 0)
        ::close(fd_);
}

static void write_all(int fd, const void* buf, size_t len) {
    const uint8_t* p = static_cast<const uint8_t*>(buf);
    while (len > 0) {
        ssize_t n = ::write(fd, p, len);
        assert(n > 0);
        p += n;
        len -= n;
    }
}

void WAL::append_put(const char* key, uint32_t key_len,
                     const char* value, uint32_t value_len,
                     uint64_t expire_ts) {

    uint32_t total_len =
        sizeof(uint8_t) + sizeof(uint32_t) * 2 +
        sizeof(uint64_t) + key_len + value_len + sizeof(uint32_t);

    uint32_t crc = 0;

    write_all(fd_, &total_len, sizeof(total_len));

    uint8_t type = static_cast<uint8_t>(WalType::PUT);
    write_all(fd_, &type, sizeof(type));

    write_all(fd_, &key_len, sizeof(key_len));
    write_all(fd_, &value_len, sizeof(value_len));
    write_all(fd_, &expire_ts, sizeof(expire_ts));

    write_all(fd_, key, key_len);
    write_all(fd_, value, value_len);

    crc = crc32(type, key_len, value_len, expire_ts,
                key, key_len, value, value_len);

    write_all(fd_, &crc, sizeof(crc));
}

void WAL::append_del(const char* key, uint32_t key_len) {

    uint32_t value_len = 0;
    uint64_t expire_ts = 0;

    uint32_t total_len =
        sizeof(uint8_t) + sizeof(uint32_t) * 2 +
        sizeof(uint64_t) + key_len + sizeof(uint32_t);

    uint32_t crc = 0;

    write_all(fd_, &total_len, sizeof(total_len));

    uint8_t type = static_cast<uint8_t>(WalType::DEL);
    write_all(fd_, &type, sizeof(type));

    write_all(fd_, &key_len, sizeof(key_len));
    write_all(fd_, &value_len, sizeof(value_len));
    write_all(fd_, &expire_ts, sizeof(expire_ts));

    write_all(fd_, key, key_len);

    crc = crc32(type, key_len, value_len, expire_ts,
                key, key_len, nullptr, 0);

    write_all(fd_, &crc, sizeof(crc));
}

void WAL::replay(MemTable& memtable) {
    ::lseek(fd_, 0, SEEK_SET);

    while (true) {
        uint32_t total_len;
        ssize_t n = ::read(fd_, &total_len, sizeof(total_len));
        if (n == 0) break;
        if (n != sizeof(total_len)) break;

        uint8_t type;
        uint32_t key_len, value_len;
        uint64_t expire_ts;

        if (::read(fd_, &type, sizeof(type)) != sizeof(type)) break;
        if (::read(fd_, &key_len, sizeof(key_len)) != sizeof(key_len)) break;
        if (::read(fd_, &value_len, sizeof(value_len)) != sizeof(value_len)) break;
        if (::read(fd_, &expire_ts, sizeof(expire_ts)) != sizeof(expire_ts)) break;

        std::string key(key_len, '\0');
        std::string value(value_len, '\0');

        if (::read(fd_, key.data(), key_len) != (ssize_t)key_len) break;
        if (value_len > 0 &&
            ::read(fd_, value.data(), value_len) != (ssize_t)value_len)
            break;

        uint32_t crc_file;
        if (::read(fd_, &crc_file, sizeof(crc_file)) != sizeof(crc_file))
            break;

        uint32_t crc_calc =
            crc32(type, key_len, value_len, expire_ts,
                  key.data(), key_len,
                  value_len ? value.data() : nullptr, value_len);

        if (crc_calc != crc_file) break;

        if (type == static_cast<uint8_t>(WalType::PUT)) {
            memtable.put(key.data(), key_len,
                         value.data(), value_len,
                         expire_ts ? (expire_ts - std::time(nullptr)) : 0);
        } else {
            memtable.del(key.data(), key_len);
        }
    }
}
void WAL::close() {
    if (fd_ >= 0) {
        ::close(fd_);
        fd_ = -1;
    }
}

void WAL::reset(const std::string& path) {
    close();
    path_ = path;
    fd_ = ::open(path_.c_str(),
                 O_CREAT | O_TRUNC | O_WRONLY | O_APPEND,
                 0644);
    assert(fd_ >= 0);
}

} // namespace mvdb
