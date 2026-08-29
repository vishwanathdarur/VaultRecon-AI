#include "util/hash.hpp"
#include "util/arena.hpp"

#include <cstring>
#include <cassert>
#include <cstdlib>
#include <ctime>

namespace mvdb {

static constexpr double MAX_LOAD = 0.7;

uint64_t HashTable::hash_key(const char* data, uint32_t len) const {
    uint64_t h = 14695981039346656037ull;
    for (uint32_t i = 0; i < len; i++) {
        h ^= (uint8_t)data[i];
        h *= 1099511628211ull;
    }
    return h;
}

HashTable::HashTable(size_t initial_capacity, Arena* arena)
    : capacity_(1), size_(0), tombstones_(0), arena_(arena) {

    while (capacity_ < initial_capacity)
        capacity_ <<= 1;

    entries_ = (Entry*)std::calloc(capacity_, sizeof(Entry));
    assert(entries_);
}

HashTable::~HashTable() {
    std::free(entries_);
}

size_t HashTable::find_slot(uint64_t hash,
                            const char* key,
                            uint32_t key_len,
                            bool for_insert) {
    size_t idx = hash & (capacity_ - 1);
    size_t first_tombstone = SIZE_MAX;

    for (;;) {
        Entry& e = entries_[idx];

        if (e.state == EntryState::EMPTY) {
            return (for_insert && first_tombstone != SIZE_MAX)
                       ? first_tombstone
                       : idx;
        }

        if (e.state == EntryState::TOMBSTONE) {
            if (for_insert && first_tombstone == SIZE_MAX)
                first_tombstone = idx;
        } else if (e.hash == hash &&
                   e.key_len == key_len &&
                   std::memcmp(e.key, key, key_len) == 0) {
            return idx;
        }

        idx = (idx + 1) & (capacity_ - 1);
    }
}

void HashTable::rehash() {
    Entry* old_entries = entries_;
    size_t old_capacity = capacity_;

    capacity_ <<= 1;
    entries_ = (Entry*)std::calloc(capacity_, sizeof(Entry));
    assert(entries_);

    size_ = 0;
    tombstones_ = 0;

    for (size_t i = 0; i < old_capacity; i++) {
        Entry& e = old_entries[i];
        if (e.state == EntryState::OCCUPIED) {
            put(e.key, e.key_len, e.value, e.value_len, e.expire_ts);
        }
    }

    std::free(old_entries);
}

bool HashTable::put(const char* key, uint32_t key_len,
                    const char* value, uint32_t value_len,
                    uint64_t expire_ts) {

    if ((size_ + tombstones_) >= capacity_ * MAX_LOAD) {
        rehash();
    }

    uint64_t h = hash_key(key, key_len);
    size_t idx = find_slot(h, key, key_len, true);
    Entry& e = entries_[idx];

    if (e.state == EntryState::OCCUPIED) {
        e.value = (char*)arena_->alloc(value_len);
        std::memcpy((void*)e.value, value, value_len);
        e.value_len = value_len;
        e.expire_ts = expire_ts;
        return true;
    }

    char* k = (char*)arena_->alloc(key_len);
    std::memcpy(k, key, key_len);

    char* v = (char*)arena_->alloc(value_len);
    std::memcpy(v, value, value_len);

    e.hash = h;
    e.key = k;
    e.key_len = key_len;
    e.value = v;
    e.value_len = value_len;
    e.expire_ts = expire_ts;
    e.state = EntryState::OCCUPIED;

    size_++;
    return true;
}

bool HashTable::get(const char* key, uint32_t key_len,
                    const char*& value_out, uint32_t& value_len_out) {

    uint64_t h = hash_key(key, key_len);
    size_t idx = find_slot(h, key, key_len, false);
    Entry& e = entries_[idx];

    if (e.state != EntryState::OCCUPIED)
        return false;

    if (e.expire_ts != 0 && e.expire_ts < (uint64_t)std::time(nullptr)) {
        e.state = EntryState::TOMBSTONE;
        size_--;
        tombstones_++;
        return false;
    }

    value_out = e.value;
    value_len_out = e.value_len;
    return true;
}

bool HashTable::del(const char* key, uint32_t key_len) {
    uint64_t h = hash_key(key, key_len);
    size_t idx = find_slot(h, key, key_len, false);
    Entry& e = entries_[idx];

    if (e.state != EntryState::OCCUPIED)
        return false;

    e.state = EntryState::TOMBSTONE;
    size_--;
    tombstones_++;
    return true;
}

} 
