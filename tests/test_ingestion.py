"""
Unit tests for data generation and ingestion.
"""

import shutil
import unittest
from ingestion.generators import SyntheticDataGenerator, calculate_standard_fee
from ingestion.loader import IngestionLoader
from recon.storage import MiniVaultDBClient


class TestIngestion(unittest.TestCase):
    def test_synthetic_generator(self):
        generator = SyntheticDataGenerator(seed=42)
        dataset = generator.generate(count=50)

        self.assertGreater(len(dataset.payments), 0)
        self.assertGreater(len(dataset.invoices), 0)
        self.assertGreater(len(dataset.settlements), 0)
        self.assertEqual(len(dataset.ground_truth), 50)

        # Verify standard fee calculations
        self.assertEqual(calculate_standard_fee("UPI", 1000.0), 0.0)
        self.assertEqual(calculate_standard_fee("CREDIT_CARD", 1000.0), 20.0)
        self.assertEqual(calculate_standard_fee("DEBIT_CARD", 1000.0), 9.0)
        self.assertEqual(calculate_standard_fee("NET_BANKING", 1000.0), 15.0)

    def test_ingestion_loader(self):
        test_dir = "./testdb_ingestion_test"
        shutil.rmtree(test_dir, ignore_errors=True)

        with MiniVaultDBClient(db_dir=test_dir, memtable_bytes=4 * 1024 * 1024) as db:
            generator = SyntheticDataGenerator(seed=123)
            dataset = generator.generate(count=100)

            loader = IngestionLoader(db)
            report = loader.load_dataset(dataset)

            self.assertGreaterEqual(report.total_records, 300)
            self.assertGreater(report.throughput_records_per_sec, 0)
            self.assertGreater(report.duration_sec, 0)

        shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

