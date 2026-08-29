#pragma once
#include <string>
#include <vector>
#include "engine/memtable.hpp"
#include "engine/wal.hpp"
using namespace std;
namespace mvdb {

class DB {
public:
    DB(const std::string& dir,
       size_t memtable_bytes);

    ~DB();

    void put(const char* key, uint32_t key_len,
             const char* value, uint32_t value_len,
             uint64_t ttl_sec = 0);

    bool get(const char* key, uint32_t key_len,
             std::string& value_out);

    void del(const char* key, uint32_t key_len);

    void put(string &key,string &value);
    std::string get(string &key);
    void del(string &key);

    std::vector<std::pair<std::string, std::string>> scan_prefix(const std::string& prefix);

private:
    void maybe_flush();
    void freeze_memtable();
    void flush_immutable();
    void load_sstables();
    void replay_wal();
    void rotate_wal();

private:
    std::string dir_;
    size_t mem_limit_;

    WAL wal_;

    MemTable* active_;
    MemTable* immutable_;

    std::vector<std::string> sst_files_;
    uint64_t next_sst_id_;
};

}
