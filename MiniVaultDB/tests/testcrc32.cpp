#include "util/crc32.hpp"
#include <cassert>
#include <cstring>
#include <iostream>

using namespace mvdb;

int main() {
    const char* data = "hello world";
    uint32_t c1 = crc32(data, std::strlen(data));
    uint32_t c2 = crc32(data, std::strlen(data));

    assert(c1 == c2);

    const char* data2 = "hello worle";
    uint32_t c3 = crc32(data2, std::strlen(data2));

    assert(c1 != c3);

    uint32_t c4 = crc32(
        1, 5, 5, 0,
        "hello", 5,
        "world", 5
    );

    uint32_t c5 = crc32(
        1, 5, 5, 0,
        "hello", 5,
        "world", 5
    );

    assert(c4 == c5);

    std::cout << "CRC32 tests passed ✅\n";
    return 0;
}
