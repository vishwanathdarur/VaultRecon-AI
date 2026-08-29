#include "db/db.hpp"
#include "engine/sstable.hpp"

#include <algorithm>
#include <sstream>
#include <ctime>
#include <filesystem>
#include <cstring>
#include <string>
#include <unordered_map>
#include <unordered_set>

namespace fs = std::filesystem;
using namespace std;
namespace mvdb {

static constexpr size_t ARENA_FACTOR = 8;

/* ================= CONSTRUCTOR / DESTRUCTOR ================= */

static void ensure_dir_exists(const std::string& dir) {
    if (!fs::exists(dir)) {
        fs::create_directories(dir);
    }
}

DB::DB(const std::string& dir,
       size_t memtable_bytes)
    : dir_(dir),
      mem_limit_(memtable_bytes),
      wal_((ensure_dir_exists(dir), dir + "/wal.log")),
      active_(new MemTable(memtable_bytes,
                           memtable_bytes * ARENA_FACTOR)),
      immutable_(nullptr),
      next_sst_id_(0) {

    load_sstables();
    replay_wal();
}


DB::~DB() {
    delete active_;
    delete immutable_;
    wal_.close();
}

/* ================= WRITE PATH ================= */

void DB::put(const char* key, uint32_t key_len,
             const char* value, uint32_t value_len,
             uint64_t ttl_sec) {

    wal_.append_put(key, key_len, value, value_len, ttl_sec);
    active_->put(key, key_len, value, value_len, ttl_sec);

    maybe_flush();
}

void DB::put(string &key,string &value) {
    put(key.data(),key.size(),value.data(),value.size(),0);
}

void DB::del(const char* key, uint32_t key_len) {
    wal_.append_del(key, key_len);
    active_->del(key, key_len);

    maybe_flush();
}

void DB::del(string &key) {
    del(key.data(),key.size());
}

/* ================= READ PATH ================= */

bool DB::get(const char* key, uint32_t key_len,
             std::string& value_out) {

    const char* v;
    uint32_t vlen;

    // 1️⃣ Active MemTable
    if (active_->get(key, key_len, v, vlen)) {
        value_out.assign(v, vlen);
        return true;
    }

    // 2️⃣ Immutable MemTable (if flushing)
    if (immutable_ && immutable_->get(key, key_len, v, vlen)) {
        value_out.assign(v, vlen);
        return true;
    }

    // 3️⃣ SSTables (newest → oldest)
    for (auto it = sst_files_.rbegin();
         it != sst_files_.rend(); ++it) {

        SSTable sst(*it);
        if (sst.get(key, key_len, value_out))
            return true;
    }

    return false;
}

string DB::get(string &key) {
    string value;
    if (get(key.data(),key.size(),value)) {
        return value;
    }
    return "";
}

std::vector<std::pair<std::string, std::string>> DB::scan_prefix(const std::string& prefix) {
    std::unordered_map<std::string, std::string> seen;
    std::unordered_set<std::string> deleted;
    uint64_t now = (uint64_t)std::time(nullptr);

    // 1. Active MemTable
    if (active_) {
        active_->for_each([&](const Entry& e) {
            if (e.key_len >= prefix.size() && std::memcmp(e.key, prefix.data(), prefix.size()) == 0) {
                std::string k(e.key, e.key_len);
                if (e.expire_ts == 0 || e.expire_ts >= now) {
                    seen[k] = std::string(e.value, e.value_len);
                } else {
                    deleted.insert(k);
                }
            }
        });
    }

    // 2. Immutable MemTable
    if (immutable_) {
        immutable_->for_each([&](const Entry& e) {
            if (e.key_len >= prefix.size() && std::memcmp(e.key, prefix.data(), prefix.size()) == 0) {
                std::string k(e.key, e.key_len);
                if (seen.find(k) == seen.end() && deleted.find(k) == deleted.end()) {
                    if (e.expire_ts == 0 || e.expire_ts >= now) {
                        seen[k] = std::string(e.value, e.value_len);
                    } else {
                        deleted.insert(k);
                    }
                }
            }
        });
    }

    // 3. SSTables (newest to oldest)
    for (auto it = sst_files_.rbegin(); it != sst_files_.rend(); ++it) {
        SSTable sst(*it);
        std::vector<std::pair<std::string, std::string>> sst_res;
        sst.scan_prefix(prefix, sst_res);
        for (auto& kv : sst_res) {
            if (seen.find(kv.first) == seen.end() && deleted.find(kv.first) == deleted.end()) {
                seen[kv.first] = std::move(kv.second);
            }
        }
    }

    std::vector<std::pair<std::string, std::string>> results;
    results.reserve(seen.size());
    for (auto& p : seen) {
        results.emplace_back(p.first, std::move(p.second));
    }
    std::sort(results.begin(), results.end(), [](const auto& a, const auto& b) {
        return a.first < b.first;
    });
    return results;
}
/* ================= FLUSH LOGIC ================= */

void DB::maybe_flush() {
    if (active_->size_bytes() >= mem_limit_) {
        freeze_memtable();
        flush_immutable();
        rotate_wal();   
    }
}


void DB::freeze_memtable() {
    immutable_ = active_;

    active_ = new MemTable(
        mem_limit_,
        mem_limit_ * ARENA_FACTOR
    );
}

void DB::flush_immutable() {
    if (!immutable_) return;

    std::vector<std::pair<std::string, std::string>> kvs;

    immutable_->for_each([&](const Entry& e) {
        if (e.expire_ts != 0 &&
            e.expire_ts < (uint64_t)std::time(nullptr))
            return;

        kvs.emplace_back(
            std::string(e.key, e.key_len),
            std::string(e.value, e.value_len)
        );
    });

    std::sort(kvs.begin(), kvs.end(),
              [](const auto& a, const auto& b) {
                  return a.first < b.first;
              });

    std::ostringstream ss;
    ss << dir_ << "/sst_" << next_sst_id_++ << ".sst";

    SSTable::build(ss.str(), kvs);
    sst_files_.push_back(ss.str());

    delete immutable_;
    immutable_ = nullptr;
}

/* ================= RECOVERY ================= */

void DB::load_sstables() {
    if (!fs::exists(dir_)) return;

    for (const auto& entry : fs::directory_iterator(dir_)) {
        if (!entry.is_regular_file()) continue;

        const auto& path = entry.path();
        if (path.extension() == ".sst") {
            sst_files_.push_back(path.string());

            // extract sst id
            std::string stem = path.stem().string(); // sst_X
            auto pos = stem.find('_');
            if (pos != std::string::npos) {
                uint64_t id = std::stoull(stem.substr(pos + 1));
                next_sst_id_ = std::max(next_sst_id_, id + 1);
            }
        }
    }

    std::sort(sst_files_.begin(), sst_files_.end());
}

void DB::replay_wal() {
    wal_.replay(*active_);
}


void DB::rotate_wal() {
    wal_.close();                 // close current fd
    wal_.reset(dir_ + "/wal.log"); // reopen fresh WAL
}

}
