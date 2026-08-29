"""
Python Client for MiniVaultDB Storage Engine via C API.
Provides high-performance key-value operations, prefix scanning,
and domain-specific indexing for normalized financial records.
"""

import os
import json
import ctypes
from typing import Optional, List, Tuple, Dict, Any

from ingestion.schemas import (
    FinancialRecord,
    PaymentRecord,
    InvoiceRecord,
    ProcessorTransaction,
    SettlementRecord,
    SettlementBatch,
    BankTransactionRecord,
    RefundRecord,
    AdjustmentRecord,
)


class MiniVaultDBRaw:
    def __init__(self, lib_path: Optional[str] = None):
        if lib_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            lib_path = os.path.join(base_dir, "MiniVaultDB", "libminivaultdb.so")

        if not os.path.exists(lib_path):
            raise FileNotFoundError(f"MiniVaultDB shared library not found at: {lib_path}. Run 'make -C MiniVaultDB' first.")

        self.lib = ctypes.CDLL(lib_path)

        # void* mvdb_open(const char* dir, size_t memtable_bytes)
        self.lib.mvdb_open.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
        self.lib.mvdb_open.restype = ctypes.c_void_p

        # void mvdb_close(void* db)
        self.lib.mvdb_close.argtypes = [ctypes.c_void_p]
        self.lib.mvdb_close.restype = None

        # int mvdb_put(void* db, const char* key, size_t key_len, const char* val, size_t val_len, uint64_t ttl_sec)
        self.lib.mvdb_put.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_size_t,
            ctypes.c_char_p,
            ctypes.c_size_t,
            ctypes.c_uint64,
        ]
        self.lib.mvdb_put.restype = ctypes.c_int

        # int mvdb_get(void* db, const char* key, size_t key_len, char** out_val, size_t* out_val_len)
        self.lib.mvdb_get.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_char_p),
            ctypes.POINTER(ctypes.c_size_t),
        ]
        self.lib.mvdb_get.restype = ctypes.c_int

        # void mvdb_free_val(char* val)
        self.lib.mvdb_free_val.argtypes = [ctypes.c_char_p]
        self.lib.mvdb_free_val.restype = None

        # int mvdb_del(void* db, const char* key, size_t key_len)
        self.lib.mvdb_del.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t]
        self.lib.mvdb_del.restype = ctypes.c_int

        # Callback signature for scan: void (*cb)(const char*, size_t, const char*, size_t, void*)
        self.SCAN_CB_TYPE = ctypes.CFUNCTYPE(
            None,
            ctypes.c_char_p,
            ctypes.c_size_t,
            ctypes.c_char_p,
            ctypes.c_size_t,
            ctypes.c_void_p,
        )

        # int mvdb_scan_prefix(void* db, const char* prefix, size_t prefix_len, cb, void* user_data)
        self.lib.mvdb_scan_prefix.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_size_t,
            self.SCAN_CB_TYPE,
            ctypes.c_void_p,
        ]
        self.lib.mvdb_scan_prefix.restype = ctypes.c_int


def _load_env_file():
    """Lightweight zero-dependency .env loader."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip("'\"")
                    if k:
                        os.environ[k] = v
        except Exception:
            pass


class MiniVaultDBClient:
    def __init__(self, db_dir: Optional[str] = None, memtable_bytes: Optional[int] = None, lib_path: Optional[str] = None):
        _load_env_file()
        if db_dir is None:
            db_dir = os.environ.get("VAULT_DB_DIR", "./data_vault")
        if memtable_bytes is None:
            try:
                mb = int(os.environ.get("MEMTABLE_SIZE_MB", "32"))
            except ValueError:
                mb = 32
            memtable_bytes = mb * 1024 * 1024

        self.db_dir = db_dir
        self.memtable_bytes = memtable_bytes
        self.raw = MiniVaultDBRaw(lib_path)
        os.makedirs(db_dir, exist_ok=True)
        self.handle = self.raw.lib.mvdb_open(db_dir.encode("utf-8"), memtable_bytes)
        if not self.handle:
            raise RuntimeError(f"Failed to open MiniVaultDB instance at {db_dir}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        if self.handle:
            self.raw.lib.mvdb_close(self.handle)
            self.handle = None

    def put(self, key: str, value: str, ttl_sec: int = 0) -> bool:
        k_bytes = key.encode("utf-8")
        v_bytes = value.encode("utf-8")
        res = self.raw.lib.mvdb_put(
            self.handle,
            k_bytes,
            len(k_bytes),
            v_bytes,
            len(v_bytes),
            ttl_sec,
        )
        return res == 1

    def get(self, key: str) -> Optional[str]:
        k_bytes = key.encode("utf-8")
        out_val = ctypes.c_char_p()
        out_len = ctypes.c_size_t()
        res = self.raw.lib.mvdb_get(
            self.handle,
            k_bytes,
            len(k_bytes),
            ctypes.byref(out_val),
            ctypes.byref(out_len),
        )
        if res == 1 and out_val.value is not None:
            val_str = out_val.value.decode("utf-8")
            self.raw.lib.mvdb_free_val(out_val)
            return val_str
        return None

    def delete(self, key: str) -> bool:
        k_bytes = key.encode("utf-8")
        return self.raw.lib.mvdb_del(self.handle, k_bytes, len(k_bytes)) == 1

    def scan_prefix(self, prefix: str) -> List[Tuple[str, str]]:
        results: List[Tuple[str, str]] = []

        def callback(k_ptr, k_len, v_ptr, v_len, udata):
            k = ctypes.string_at(k_ptr, k_len).decode("utf-8")
            v = ctypes.string_at(v_ptr, v_len).decode("utf-8")
            results.append((k, v))

        c_cb = self.raw.SCAN_CB_TYPE(callback)
        p_bytes = prefix.encode("utf-8")
        self.raw.lib.mvdb_scan_prefix(
            self.handle,
            p_bytes,
            len(p_bytes),
            c_cb,
            None,
        )
        return results

    # ================= DOMAIN SPECIFIC HELPERS =================

    def put_record(self, record: FinancialRecord) -> bool:
        """
        Store normalized financial record in MiniVaultDB and write secondary index pointers.
        """
        primary_key = record.to_key()
        json_val = record.model_dump_json()
        if not self.put(primary_key, json_val):
            return False

        # Secondary Temporal Index: IDX:MERCHANT:<merchant>:<timestamp>:<type>:<id> -> primary_key
        temp_key = record.to_merchant_temporal_key()
        self.put(temp_key, primary_key)

        # Entity Secondary Indexes
        if isinstance(record, (PaymentRecord, InvoiceRecord)):
            self.put(record.to_order_key(), primary_key)
        elif isinstance(record, ProcessorTransaction):
            self.put(record.to_order_key(), primary_key)
            batch_k = record.to_batch_key()
            if batch_k:
                self.put(batch_k, primary_key)
        elif isinstance(record, SettlementRecord):
            self.put(record.to_txn_key(), primary_key)
            batch_k = record.to_batch_key()
            if batch_k:
                self.put(batch_k, primary_key)
        elif isinstance(record, SettlementBatch):
            self.put(record.to_ref_key(), primary_key)
        elif isinstance(record, BankTransactionRecord):
            self.put(record.to_ref_key(), primary_key)
        elif isinstance(record, RefundRecord):
            self.put(record.to_order_key(), primary_key)
            self.put(record.to_txn_key(), primary_key)

        return True

    def get_record(self, record_type: str, record_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve raw record by record_type and record_id."""
        key = f"REC:{record_type.upper()}:{record_id}"
        val = self.get(key)
        if val:
            return json.loads(val)
        return None

    def scan_merchant_window(
        self,
        merchant_id: str,
        start_ts: int,
        end_ts: int,
        record_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query temporal window for merchant using MiniVaultDB's prefix scan.
        """
        prefix = f"IDX:MERCHANT:{merchant_id}:"
        index_entries = self.scan_prefix(prefix)
        records: List[Dict[str, Any]] = []

        for idx_key, primary_key in index_entries:
            parts = idx_key.split(":")
            if len(parts) >= 6:
                ts = int(parts[3])
                rec_type = parts[4]
                if start_ts <= ts <= end_ts:
                    if record_type is None or rec_type == record_type.upper():
                        raw_json = self.get(primary_key)
                        if raw_json:
                            records.append(json.loads(raw_json))
        return records
