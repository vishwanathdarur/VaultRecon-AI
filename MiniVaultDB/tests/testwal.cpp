#include "engine/wal.hpp"
#include <cassert>
#include <cstring>
#include <iostream>
#include <unistd.h>

using namespace mvdb;

int main() {
    const char* path = "test.wal";
    ::unlink(path);

    {
        WAL wal(path);
        MemTable mt(1024 * 1024, 1024 * 1024 * 8);

        wal.append_put("a", 1, "1", 1, 0);
        wal.append_put("b", 1, "2", 1, 0);
        wal.append_del("a", 1);
    }

    {
        WAL wal(path);
        MemTable mt(1024 * 1024, 1024 * 1024 * 8);

        wal.replay(mt);

        const char* v;
        uint32_t len;

        assert(!mt.get("a", 1, v, len));
        assert(mt.get("b", 1, v, len));
        assert(std::memcmp(v, "2", 1) == 0);
    }

    std::cout << "WAL tests passed ✅\n";
    ::unlink(path);
    return 0;
}
