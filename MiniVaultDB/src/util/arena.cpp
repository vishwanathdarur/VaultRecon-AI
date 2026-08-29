#include "util/arena.hpp"
#include <cstdlib>
#include <cassert>

namespace mvdb {

Arena::Arena(size_t capacity)
    : capacity_(capacity), offset_(0) {
    base_ = static_cast<uint8_t*>(std::malloc(capacity_));
    assert(base_ && "Arena allocation failed");
}

Arena::~Arena() {
    std::free(base_);
}

void* Arena::alloc(size_t size, size_t align) {
    size_t current = reinterpret_cast<size_t>(base_ + offset_);
    size_t aligned = (current + (align - 1)) & ~(align - 1);
    size_t new_offset = aligned - reinterpret_cast<size_t>(base_) + size;

    assert(new_offset <= capacity_ && "Arena out of memory");

    offset_ = new_offset;
    return reinterpret_cast<void*>(aligned);
}

}
