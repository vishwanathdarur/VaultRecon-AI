#include "util/hash.hpp"
#include "util/arena.hpp"
#include <cassert>
#include <cstring>
#include <iostream>

using namespace mvdb;
using namespace std;
int main() {
    Arena arena(1024 * 1024);
    HashTable ht(16, &arena);

    const char* val;
    uint32_t val_len;

    /* insert */
    assert(ht.put("key1", 4, "value1", 6));
    assert(ht.get("key1", 4, val, val_len));
    assert(val_len == 6);
    assert(std::memcmp(val, "value1", 6) == 0);
    cout << val_len ;
    /* overwrite */
    assert(ht.put("key1", 4, "value2", 4));
    assert(ht.get("key1", 4, val, val_len));
    assert(std::memcmp(val, "value2", 4) == 0);

    /* delete */
    assert(ht.del("key1", 4));
    assert(!ht.get("key1", 4, val, val_len));

    /* reinsert after delete */
    assert(ht.put("key1", 4, "value3", 6));
    assert(ht.get("key1", 4, val, val_len));
    assert(std::memcmp(val, "value3", 6) == 0);

    /* collision stress */
    for (int i = 0; i < 1000; i++) {
        char k[16];
        char v[16];
        std::snprintf(k, sizeof(k), "k%d", i);
        std::snprintf(v, sizeof(v), "v%d", i);
        assert(ht.put(k, std::strlen(k), v, std::strlen(v)));
    }

    cout << "All hash table tests passed ✅\n";
    return 0;
}
