#include "db/c_api.h"
#include "db/db.hpp"
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

struct mvdb_db_handle {
    mvdb::DB* instance;
};

extern "C" {

mvdb_t* mvdb_open(const char* dir, size_t memtable_bytes) {
    if (!dir) return nullptr;
    try {
        mvdb_t* handle = new mvdb_t();
        handle->instance = new mvdb::DB(std::string(dir), memtable_bytes);
        return handle;
    } catch (...) {
        return nullptr;
    }
}

void mvdb_close(mvdb_t* db) {
    if (!db) return;
    delete db->instance;
    delete db;
}

int mvdb_put(mvdb_t* db, const char* key, size_t key_len,
             const char* val, size_t val_len, uint64_t ttl_sec) {
    if (!db || !db->instance || !key) return 0;
    try {
        db->instance->put(key, (uint32_t)key_len, val ? val : "", (uint32_t)val_len, ttl_sec);
        return 1;
    } catch (...) {
        return 0;
    }
}

int mvdb_get(mvdb_t* db, const char* key, size_t key_len,
             char** out_val, size_t* out_val_len) {
    if (!db || !db->instance || !key || !out_val || !out_val_len) return 0;
    try {
        std::string res;
        bool ok = db->instance->get(key, (uint32_t)key_len, res);
        if (!ok) {
            *out_val = nullptr;
            *out_val_len = 0;
            return 0;
        }
        *out_val_len = res.size();
        *out_val = (char*)std::malloc(res.size() + 1);
        if (*out_val) {
            std::memcpy(*out_val, res.data(), res.size());
            (*out_val)[res.size()] = '\0';
            return 1;
        }
        return 0;
    } catch (...) {
        return 0;
    }
}

void mvdb_free_val(char* val) {
    if (val) {
        std::free(val);
    }
}

int mvdb_del(mvdb_t* db, const char* key, size_t key_len) {
    if (!db || !db->instance || !key) return 0;
    try {
        db->instance->del(key, (uint32_t)key_len);
        return 1;
    } catch (...) {
        return 0;
    }
}

int mvdb_scan_prefix(mvdb_t* db, const char* prefix, size_t prefix_len,
                     mvdb_scan_callback cb, void* user_data) {
    if (!db || !db->instance || !prefix || !cb) return 0;
    try {
        std::string p(prefix, prefix_len);
        auto results = db->instance->scan_prefix(p);
        for (const auto& kv : results) {
            cb(kv.first.data(), kv.first.size(),
               kv.second.data(), kv.second.size(),
               user_data);
        }
        return (int)results.size();
    } catch (...) {
        return 0;
    }
}

}

