#pragma once
#include <cstdint>
#include <cstddef>

namespace mvdb {

/*
 * CRC32 utility for WAL corruption detection
 */
uint32_t crc32(const void* data, size_t len);

/*
 * Helper to CRC multiple fields (used by WAL)
 */
uint32_t crc32(uint8_t type,
               uint32_t key_len,
               uint32_t value_len,
               uint64_t expire_ts,
               const void* key, size_t key_size,
               const void* value, size_t value_size);

} // namespace mvdb
