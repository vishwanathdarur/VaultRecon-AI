#include "engine/sstable.hpp"
#include <cassert>
#include <iostream>
#include <unistd.h>

using namespace mvdb;

int main() {
    const char* path = "test.sst";
    ::unlink(path);

    std::vector<std::pair<std::string, std::string>> kvs = {
        {"a", "1"},
        {"b", "2"},
        {"c", "3"}
    };

    SSTable::build(path, kvs);

    SSTable sst(path);

    std::string val;
    assert(sst.get("a", 1, val) && val == "1");
    assert(sst.get("b", 1, val) && val == "2");
    assert(sst.get("c", 1, val) && val == "3");
    assert(!sst.get("d", 1, val));

    std::cout << "SSTable tests passed ✅\n";
    ::unlink(path);
    return 0;
}
