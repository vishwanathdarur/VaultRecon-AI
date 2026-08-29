#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace mvdb {

class SSTable {
public:
    /* Writer */
    static void build(const std::string& path,
                      const std::vector<std::pair<std::string, std::string>>& kvs);

    /* Reader */
    explicit SSTable(const std::string& path);
    ~SSTable();

    bool get(const char* key, uint32_t key_len,
             std::string& value_out);

    bool read_record(uint64_t offset, std::string& key_out,
                     std::string& val_out, uint64_t& expire_ts_out);

    void scan_prefix(const std::string& prefix,
                     std::vector<std::pair<std::string, std::string>>& results);

private:
    void load_index();

private:
    int fd_;
    uint64_t index_offset_;
    uint64_t index_size_;

    struct IndexEntry {
        std::string key;
        uint64_t offset;
    };

    std::vector<IndexEntry> index_;
};

} // namespace mvdb
