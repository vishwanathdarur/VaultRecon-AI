"""
Unit tests for Python MiniVaultDB storage client.
"""

import shutil
import unittest
from recon.storage import MiniVaultDBClient
from ingestion.schemas import PaymentRecord


class TestStorage(unittest.TestCase):
    def test_minivault_basic_put_get(self):
        test_dir = "./testdb_py_basic"
        shutil.rmtree(test_dir, ignore_errors=True)

        with MiniVaultDBClient(db_dir=test_dir, memtable_bytes=1024 * 1024) as db:
            self.assertTrue(db.put("test_key_1", "test_value_1"))
            self.assertEqual(db.get("test_key_1"), "test_value_1")
            self.assertIsNone(db.get("non_existent"))

            # Overwrite
            self.assertTrue(db.put("test_key_1", "updated_value"))
            self.assertEqual(db.get("test_key_1"), "updated_value")

            # Delete
            self.assertTrue(db.delete("test_key_1"))
            self.assertIsNone(db.get("test_key_1"))

        shutil.rmtree(test_dir, ignore_errors=True)

    def test_minivault_prefix_scan(self):
        test_dir = "./testdb_py_scan"
        shutil.rmtree(test_dir, ignore_errors=True)

        with MiniVaultDBClient(db_dir=test_dir, memtable_bytes=1024 * 1024) as db:
            db.put("USER:1", "Alice")
            db.put("USER:2", "Bob")
            db.put("USER:3", "Charlie")
            db.put("ORDER:100", "Widget")

            scanned = db.scan_prefix("USER:")
            self.assertEqual(len(scanned), 3)
            keys = [k for k, _ in scanned]
            self.assertIn("USER:1", keys)
            self.assertIn("USER:2", keys)
            self.assertIn("USER:3", keys)

        shutil.rmtree(test_dir, ignore_errors=True)

    def test_financial_record_indexing(self):
        test_dir = "./testdb_py_records"
        shutil.rmtree(test_dir, ignore_errors=True)

        with MiniVaultDBClient(db_dir=test_dir, memtable_bytes=1024 * 1024) as db:
            pay = PaymentRecord(
                merchant_id="MERCH_01",
                transaction_id="TXN_999",
                order_id="ORD_888",
                customer_id="CUST_111",
                amount=500.0,
                payment_method="UPI",
                timestamp=1714500000,
            )
            self.assertTrue(db.put_record(pay))

            # Retrieve record
            rec = db.get_record("PAYMENT", "TXN_999")
            self.assertIsNotNone(rec)
            self.assertEqual(rec["amount"], 500.0)
            self.assertEqual(rec["order_id"], "ORD_888")

            # Temporal merchant scan
            window_recs = db.scan_merchant_window("MERCH_01", 1714499000, 1714501000)
            self.assertEqual(len(window_recs), 1)
            self.assertEqual(window_recs[0]["transaction_id"], "TXN_999")

        shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

