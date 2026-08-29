#include "engine/memtable.hpp"

#include <cassert>
#include <cstring>
#include <iostream>
#include <thread>
#include <chrono>

using namespace mvdb;

int main() {
    MemTable mt(1024 * 1024, 1024 * 1024 * 8); // 1 MB limit, 8 MB arena

    const char* val;
    uint32_t val_len;

    /* basic put/get */
    assert(mt.put("a", 1, "1", 1));
    assert(mt.get("a", 1, val, val_len));
    assert(val_len == 1);
    assert(std::memcmp(val, "1", 1) == 0);

    /* overwrite */
    assert(mt.put("a", 1, "2", 1));
    assert(mt.get("a", 1, val, val_len));
    assert(std::memcmp(val, "2", 1) == 0);

    /* delete */
    assert(mt.del("a", 1));
    assert(!mt.get("a", 1, val, val_len));

    /* reinsert after delete */
    assert(mt.put("a", 1, "3", 1));
    assert(mt.get("a", 1, val, val_len));
    assert(std::memcmp(val, "3", 1) == 0);

    /* TTL test */
    assert(mt.put("ttl", 3, "x", 1, 1)); // expires in 1 second
    assert(mt.get("ttl", 3, val, val_len));

    std::this_thread::sleep_for(std::chrono::seconds(2));
    assert(!mt.get("ttl", 3, val, val_len));

    /* stress insert */
    for (int i = 0; i < 1000; i++) {
        char k[16];
        char v[16];
        std::snprintf(k, sizeof(k), "k%d", i);
        std::snprintf(v, sizeof(v), "v%d", i);
        assert(mt.put(k, std::strlen(k), v, std::strlen(v)));
    }

    std::cout << "All MemTable tests passed ✅\n";
    std::cout << "Entries: " << mt.entry_count() << "\n";
    std::cout << "Bytes used: " << mt.size_bytes() << "\n";

    return 0;
}
