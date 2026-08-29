#include "db/c_api.h"
#include <cassert>
#include <iostream>
#include <cstring>
#include <vector>
#include <string>

int main() {
    ::system("rm -rf testdb_capi && mkdir -p testdb_capi");

    mvdb_t* db = mvdb_open("testdb_capi", 1024 * 1024);
    assert(db != nullptr);

    // Test PUT & GET
    const char* k1 = "REC:PAYMENT:101";
    const char* v1 = "{\"amount\": 100.0, \"status\": \"SUCCESS\"}";
    assert(mvdb_put(db, k1, std::strlen(k1), v1, std::strlen(v1), 0) == 1);

    const char* k2 = "REC:PAYMENT:102";
    const char* v2 = "{\"amount\": 250.0, \"status\": \"SUCCESS\"}";
    assert(mvdb_put(db, k2, std::strlen(k2), v2, std::strlen(v2), 0) == 1);

    const char* k3 = "REC:INVOICE:201";
    const char* v3 = "{\"amount\": 100.0, \"status\": \"PAID\"}";
    assert(mvdb_put(db, k3, std::strlen(k3), v3, std::strlen(v3), 0) == 1);

    char* out_val = nullptr;
    size_t out_len = 0;
    assert(mvdb_get(db, k1, std::strlen(k1), &out_val, &out_len) == 1);
    assert(std::string(out_val, out_len) == v1);
    mvdb_free_val(out_val);

    // Test Prefix Scan
    std::vector<std::pair<std::string, std::string>> scanned;
    auto scan_cb = [](const char* k, size_t kl, const char* v, size_t vl, void* udata) {
        auto* vec = static_cast<std::vector<std::pair<std::string, std::string>>*>(udata);
        vec->emplace_back(std::string(k, kl), std::string(v, vl));
    };

    const char* prefix = "REC:PAYMENT:";
    int count = mvdb_scan_prefix(db, prefix, std::strlen(prefix), scan_cb, &scanned);
    assert(count == 2);
    assert(scanned.size() == 2);
    assert(scanned[0].first == "REC:PAYMENT:101");
    assert(scanned[1].first == "REC:PAYMENT:102");

    // Test Delete
    assert(mvdb_del(db, k1, std::strlen(k1)) == 1);
    assert(mvdb_get(db, k1, std::strlen(k1), &out_val, &out_len) == 0);

    mvdb_close(db);
    std::cout << "MiniVaultDB C API & Prefix Scan test passed ✅\n";
    return 0;
}

