#include "engine/memtable.hpp"
#include <ctime>

namespace mvdb {

MemTable::MemTable(size_t logical_limit,
                   size_t arena_capacity)
    : arena_(arena_capacity),
      table_(16, &arena_),
      bytes_(0),
      logical_limit_(logical_limit) {}


uint64_t MemTable::compute_expire_ts(uint64_t ttl_seconds) const {
    if (ttl_seconds == 0)
        return 0;
    return static_cast<uint64_t>(std::time(nullptr)) + ttl_seconds;
}

bool MemTable::put(const char* key, uint32_t key_len,
                   const char* value, uint32_t value_len,
                   uint64_t ttl_seconds) {

    uint64_t expire_ts = compute_expire_ts(ttl_seconds);

    bool ok = table_.put(key, key_len,
                         value, value_len,
                         expire_ts);

    if (ok) {
        bytes_ += key_len + value_len;
    }
    return ok;
}

bool MemTable::get(const char* key, uint32_t key_len,
                   const char*& value_out, uint32_t& value_len_out) {

    return table_.get(key, key_len, value_out, value_len_out);
}

bool MemTable::del(const char* key, uint32_t key_len) {

    bool ok = table_.del(key, key_len);

    if (ok) {
        bytes_ += key_len;
    }
    return ok;
}

}
