#include "db/db.hpp"
#include <cassert>
#include <iostream>
#include <unistd.h>

using namespace mvdb;

int main() {
    ::system("rm -rf testdb1 && mkdir testdb");

    DB db("testdb1", 1024 * 1024);

    db.put("a", 1, "1", 1);
    db.put("b", 1, "2", 1);

    std::string v;
    assert(db.get("a", 1, v) && v == "1");
    assert(db.get("b", 1, v) && v == "2");

    db.del("a", 1);
    assert(!db.get("a", 1, v));

    std::cout << "Basic DB test passed ✅\n";
    return 0;
}
