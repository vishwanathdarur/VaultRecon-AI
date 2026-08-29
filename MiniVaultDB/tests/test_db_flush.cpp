#include "db/db.hpp"
#include <cassert>
#include <iostream>
#include <unistd.h>
#include <cstring>

using namespace mvdb;

int main() {
    ::system("rm -rf testdb && mkdir testdb");

    DB db("testdb", 64); 

    for (int i = 0; i < 20; i++) {
        char k[8], v[8];
        std::snprintf(k, sizeof(k), "k%d", i);
        std::snprintf(v, sizeof(v), "v%d", i);
        db.put(k, std::strlen(k), v, std::strlen(v));
    }

    std::string val;
    for (int i = 0; i < 20; i++) {
        char k[8];
        std::snprintf(k, sizeof(k), "k%d", i);
        assert(db.get(k, std::strlen(k), val));
    }

    std::cout << "DB flush test passed ✅\n";
    return 0;
}
