#pragma once
#include <cstddef>
#include <cstdint>

namespace mvdb {

class Arena {
public:
    explicit Arena(size_t capacity);
    ~Arena();

    void* alloc(size_t size, size_t align = 8);
    size_t used() const { return offset_; }

private:
    uint8_t* base_;
    size_t capacity_;
    size_t offset_;
};

}
