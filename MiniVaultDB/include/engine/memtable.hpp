#pragma once
#include <cstdint>
#include <cstddef>

#include "util/hash.hpp"
#include "util/arena.hpp"

namespace mvdb {

/*
 * MemTable
 * --------
 * - Owns Arena (memory lifetime)
 * - Owns HashTable (storage)
 * - Defines DB semantics (put/get/del/ttl)
 * - Tracks logical memory usage
 */
class MemTable {
public:
    explicit MemTable(size_t logical_limit,
                  size_t arena_capacity);


    bool put(const char* key, uint32_t key_len,
             const char* value, uint32_t value_len,
             uint64_t ttl_seconds = 0);

    bool get(const char* key, uint32_t key_len,
             const char*& value_out, uint32_t& value_len_out);

    bool del(const char* key, uint32_t key_len);

    size_t size_bytes() const { return bytes_; }
    size_t entry_count() const { return table_.size(); }

    template <typename F>
    void for_each(F&& fn) {
        table_.for_each(fn);
    }

private:
    uint64_t compute_expire_ts(uint64_t ttl_seconds) const;

private:
    Arena arena_;
    HashTable table_;
    size_t bytes_;
    size_t logical_limit_;
};

}
