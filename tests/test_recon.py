"""
Unit tests for deterministic reconciliation engine and exception generation.
"""

import shutil
import unittest
from ingestion.generators import SyntheticDataGenerator
from ingestion.loader import IngestionLoader
from recon.storage import MiniVaultDBClient
from recon.matcher import ReconciliationEngine


class TestReconciliationEngine(unittest.TestCase):
    def setUp(self):
        self.test_dir = "./testdb_recon_unit"
        shutil.rmtree(self.test_dir, ignore_errors=True)
        self.db = MiniVaultDBClient(db_dir=self.test_dir, memtable_bytes=4 * 1024 * 1024)

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_reconcile_dataset(self):
        generator = SyntheticDataGenerator(seed=42)
        dataset = generator.generate(count=50)

        loader = IngestionLoader(self.db)
        loader.load_dataset(dataset)

        engine = ReconciliationEngine(self.db)
        report = engine.reconcile_all()

        self.assertEqual(report.total_evaluated, len(dataset.payments))
        self.assertGreater(report.matched_count, 0)
        self.assertGreater(report.exception_count, 0)
        self.assertEqual(report.matched_count + report.exception_count, report.total_evaluated)

        # Check matched case properties
        first_match = report.matches[0]
        self.assertTrue(first_match.match_id.startswith("MATCH_"))
        self.assertEqual(first_match.confidence, 1.0)

        # Check exception case properties
        first_exc = report.exceptions[0]
        self.assertTrue(first_exc.exception_id.startswith("EXC_"))
        self.assertIn(first_exc.exception_type, [
            "AMOUNT_MISMATCH",
            "FEE_DISCREPANCY",
            "FEE_MISMATCH",
            "NOISY_BANK_REFERENCE",
            "MISSING_SETTLEMENT",
            "MISSING_PROCESSOR",
            "UNMATCHED_BANK_CREDIT",
        ])
        self.assertGreater(len(first_exc.audit_trail), 0)


if __name__ == "__main__":
    unittest.main()

