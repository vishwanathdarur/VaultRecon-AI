#include "util/crc32.hpp"

namespace mvdb {

static uint32_t crc_table[256];
static bool table_init = false;

static void init_crc_table() {
    for (uint32_t i = 0; i < 256; i++) {
        uint32_t c = i;
        for (int j = 0; j < 8; j++) {
            if (c & 1)
                c = 0xEDB88320 ^ (c >> 1);
            else
                c >>= 1;
        }
        crc_table[i] = c;
    }
    table_init = true;
}

uint32_t crc32(const void* data, size_t len) {
    if (!table_init)
        init_crc_table();

    uint32_t c = 0xFFFFFFFF;
    const uint8_t* p = static_cast<const uint8_t*>(data);

    for (size_t i = 0; i < len; i++) {
        c = crc_table[(c ^ p[i]) & 0xFF] ^ (c >> 8);
    }

    return c ^ 0xFFFFFFFF;
}

uint32_t crc32(uint8_t type,
               uint32_t key_len,
               uint32_t value_len,
               uint64_t expire_ts,
               const void* key, size_t key_size,
               const void* value, size_t value_size) {

    uint32_t c = 0xFFFFFFFF;
    if (!table_init)
        init_crc_table();

    auto mix = [&](const void* d, size_t n) {
        const uint8_t* p = static_cast<const uint8_t*>(d);
        for (size_t i = 0; i < n; i++) {
            c = crc_table[(c ^ p[i]) & 0xFF] ^ (c >> 8);
        }
    };

    mix(&type, sizeof(type));
    mix(&key_len, sizeof(key_len));
    mix(&value_len, sizeof(value_len));
    mix(&expire_ts, sizeof(expire_ts));

    mix(key, key_size);
    if (value && value_size > 0)
        mix(value, value_size);

    return c ^ 0xFFFFFFFF;
}

} 