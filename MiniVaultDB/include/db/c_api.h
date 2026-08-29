#ifndef MINIVAULTDB_C_API_H
#define MINIVAULTDB_C_API_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct mvdb_db_handle mvdb_t;

/**
 * Open or create a MiniVaultDB instance at the given directory path.
 */
mvdb_t* mvdb_open(const char* dir, size_t memtable_bytes);

/**
 * Close and release the MiniVaultDB instance.
 */
void mvdb_close(mvdb_t* db);

/**
 * Insert or update a key-value pair.
 * Returns 1 on success, 0 on failure.
 */
int mvdb_put(mvdb_t* db, const char* key, size_t key_len,
             const char* val, size_t val_len, uint64_t ttl_sec);

/**
 * Retrieve a value for a given key.
 * On success, *out_val will be populated with a malloc'd null-terminated buffer,
 * *out_val_len with byte size, and returns 1.
 * If not found, returns 0.
 * Memory allocated in *out_val must be freed with mvdb_free_val().
 */
int mvdb_get(mvdb_t* db, const char* key, size_t key_len,
             char** out_val, size_t* out_val_len);

/**
 * Free memory allocated by mvdb_get.
 */
void mvdb_free_val(char* val);

/**
 * Delete a key from the database.
 * Returns 1 on success, 0 on failure.
 */
int mvdb_del(mvdb_t* db, const char* key, size_t key_len);

/**
 * Callback for scan iterations.
 */
typedef void (*mvdb_scan_callback)(const char* key, size_t key_len,
                                   const char* val, size_t val_len,
                                   void* user_data);

/**
 * Scan all keys matching the given prefix.
 * For each matching key-value, calls cb(key, key_len, val, val_len, user_data).
 * Returns the total count of matched records.
 */
int mvdb_scan_prefix(mvdb_t* db, const char* prefix, size_t prefix_len,
                     mvdb_scan_callback cb, void* user_data);

#ifdef __cplusplus
}
#endif

#endif // MINIVAULTDB_C_API_H

