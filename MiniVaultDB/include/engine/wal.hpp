#pragma once
#include <cstdint>
#include <string>

#include "engine/memtable.hpp"

namespace mvdb {

enum class WalType : uint8_t {
    PUT = 1,
    DEL = 2
};

class WAL {
public:
    explicit WAL(const std::string& path);
    ~WAL();

    void append_put(const char* key, uint32_t key_len,
                    const char* value, uint32_t value_len,
                    uint64_t expire_ts);

    void append_del(const char* key, uint32_t key_len);

    void replay(MemTable& memtable);
    void close();
    void reset(const std::string& path);

private:
    int fd_;
    std::string path_;
};

}
