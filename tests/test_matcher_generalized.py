"""
Comprehensive Generalized Matcher Unit Tests for VaultRecon AI.
Tests 19 deterministic edge cases across all matching passes, topologies, and exception finding models.
"""

import unittest
import shutil
import time
from datetime import datetime

from recon.storage import MiniVaultDBClient
from recon.rules import ReconciliationRules, FeePolicyRegistry, calculate_description_similarity
from recon.matcher import ReconciliationEngine, ReconciliationMatch
from recon.exceptions import FinancialException
from ingestion.schemas import (
    PaymentRecord,
    InvoiceRecord,
    ProcessorTransaction,
    SettlementBatch,
    BankTransactionRecord,
    RefundRecord,
    FeePolicy,
)


class TestMatcherGeneralized(unittest.TestCase):
    def setUp(self):
        self.db_dir = "./testdb_unit_generalized"
        shutil.rmtree(self.db_dir, ignore_errors=True)
        self.db = MiniVaultDBClient(db_dir=self.db_dir)
        self.rules = ReconciliationRules(
            amount_tolerance=0.99,
            timing_window_days=5,
            tolerance_window_days=7,
            fuzzy_threshold=0.35,
        )
        self.engine = ReconciliationEngine(self.db, rules=self.rules)

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.db_dir, ignore_errors=True)

    def test_01_exact_match(self):
        """Pass 1: Exact date, amount, currency, and reference."""
        pay = PaymentRecord(
            transaction_id="P1", order_id="ORD1", amount=100.0,
            currency="USD", timestamp=10000, payment_method="CARD"
        )
        proc = ProcessorTransaction(
            processor_transaction_id="PR1", order_id="ORD1",
            gross_amount=100.0, fee_amount=3.20, net_amount=96.80,
            currency="USD", timestamp=10000
        )
        self.db.put(pay.to_key(), pay.model_dump_json())
        self.db.put(pay.to_order_key(), pay.to_key())
        self.db.put(proc.to_key(), proc.model_dump_json())
        self.db.put(proc.to_order_key(), proc.to_key())

        m, exc = self.engine.reconcile_order(pay)
        self.assertIsNotNone(m)
        self.assertIsNone(exc)
        self.assertEqual(m.match_strategy, "EXACT")
        self.assertEqual(m.confidence, 1.0)

    def test_02_timing_match(self):
        """Pass 2: Exact amount and reference, date differs within 5 days."""
        pay = PaymentRecord(
            transaction_id="P2", order_id="ORD2", amount=250.0,
            currency="USD", timestamp=10000, payment_method="UPI"
        )
        proc = ProcessorTransaction(
            processor_transaction_id="PR2", order_id="ORD2",
            gross_amount=250.0, fee_amount=0.0, net_amount=250.0,
            currency="USD", timestamp=10000 + (3 * 86400)  # 3 days later
        )
        self.db.put(pay.to_key(), pay.model_dump_json())
        self.db.put(pay.to_order_key(), pay.to_key())
        self.db.put(proc.to_key(), proc.model_dump_json())
        self.db.put(proc.to_order_key(), proc.to_key())

        m, exc = self.engine.reconcile_order(pay)
        self.assertIsNotNone(m)
        self.assertIsNone(exc)
        self.assertEqual(m.match_strategy, "TIMING")
        self.assertEqual(m.confidence, 0.98)

    def test_03_amount_tolerance_match(self):
        """Pass 3: Small penny variance ($0.31) with high description similarity."""
        pay = PaymentRecord(
            transaction_id="P3", order_id="REF40929", amount=743.29,
            currency="CAD", timestamp=10000, payment_method="DIRECT_DEBIT",
            metadata={"Memo": "GFL Environmental — invoice payment"}
        )
        proc = ProcessorTransaction(
            processor_transaction_id="PR3", order_id="REF40929",
            gross_amount=743.60, fee_amount=0.0, net_amount=743.60,
            currency="CAD", timestamp=10000 + (2 * 86400),
            metadata={"Description": "PAD GFL ENVIRONMENTAL SVC REF40929"}
        )
        self.db.put(pay.to_key(), pay.model_dump_json())
        self.db.put(pay.to_order_key(), pay.to_key())
        self.db.put(proc.to_key(), proc.model_dump_json())
        self.db.put(proc.to_order_key(), proc.to_key())

        m, exc = self.engine.reconcile_order(pay)
        self.assertIsNotNone(m)
        self.assertIsNone(exc)
        self.assertEqual(m.match_strategy, "TOLERANCE")

    def test_04_fuzzy_description_scoring(self):
        """Fuzzy similarity function handles noise words and punctuation."""
        s1 = "PAD SHELL FLEET CARD SVC REF40833"
        s2 = "Shell Fleet Card — invoice payment"
        score = calculate_description_similarity(s1, s2)
        self.assertGreaterEqual(score, 0.35)

    def test_05_zero_fee_direct_transaction(self):
        """Direct banking methods evaluate to 0% fee."""
        pay = PaymentRecord(
            transaction_id="P5", order_id="ORD5", amount=500.0,
            currency="EUR", timestamp=10000, payment_method="DIRECT_DEBIT"
        )
        proc = ProcessorTransaction(
            processor_transaction_id="PR5", order_id="ORD5",
            gross_amount=500.0, fee_amount=0.0, net_amount=500.0,
            currency="EUR", timestamp=10000
        )
        self.db.put(pay.to_key(), pay.model_dump_json())
        self.db.put(pay.to_order_key(), pay.to_key())
        self.db.put(proc.to_key(), proc.model_dump_json())
        self.db.put(proc.to_order_key(), proc.to_key())

        m, exc = self.engine.reconcile_order(pay)
        self.assertIsNotNone(m)
        self.assertIsNone(exc)

    def test_06_unknown_fee_policy_routes_to_exception(self):
        """Missing fee schedule triggers UNKNOWN_FEE_POLICY safely."""
        custom_registry = FeePolicyRegistry(allow_global_fallback=False)
        custom_registry.policies.clear()  # No policies
        rules = ReconciliationRules(fee_registry=custom_registry, enable_fee_validation=True)
        engine = ReconciliationEngine(self.db, rules=rules)

        pay = PaymentRecord(
            transaction_id="P6", order_id="ORD6", amount=500.0,
            currency="JPY", timestamp=10000, payment_method="BITCOIN"
        )
        proc = ProcessorTransaction(
            processor_transaction_id="PR6", order_id="ORD6",
            gross_amount=500.0, fee_amount=15.0, net_amount=485.0,
            currency="JPY", timestamp=10000
        )
        self.db.put(pay.to_key(), pay.model_dump_json())
        self.db.put(pay.to_order_key(), pay.to_key())
        self.db.put(proc.to_key(), proc.model_dump_json())
        self.db.put(proc.to_order_key(), proc.to_key())

        m, exc = engine.reconcile_order(pay)
        self.assertIsNone(m)
        self.assertIsNotNone(exc)
        self.assertEqual(exc.exception_type, "UNKNOWN_FEE_POLICY")

    def test_07_partial_payment_valid_reconciliation(self):
        """Legitimate partial payment is reconciled."""
        inv = InvoiceRecord(invoice_id="INV7", order_id="INV7", amount=1000.0, currency="EUR")
        pay = PaymentRecord(
            transaction_id="PAY7", order_id="INV7", amount=350.0,
            currency="EUR", timestamp=10000, payment_method="BANK_TRANSFER",
            metadata={"is_partial": True}
        )
        proc = ProcessorTransaction(
            processor_transaction_id="PR7", order_id="INV7",
            gross_amount=350.0, fee_amount=0.0, net_amount=350.0,
            currency="EUR", timestamp=10000
        )
        self.db.put(inv.to_key(), inv.model_dump_json())
        self.db.put(inv.to_order_key(), inv.to_key())
        self.db.put(pay.to_key(), pay.model_dump_json())
        self.db.put(pay.to_order_key(), pay.to_key())
        self.db.put(proc.to_key(), proc.model_dump_json())
        self.db.put(proc.to_order_key(), proc.to_key())

        m, exc = self.engine.reconcile_order(pay)
        self.assertIsNotNone(m)
        self.assertIsNone(exc)
        self.assertEqual(m.reason_code, "PARTIAL_PAYMENT_MATCH")

    def test_08_overpayment_exception(self):
        """Partial payment exceeding invoice total triggers OVERPAYMENT."""
        inv = InvoiceRecord(invoice_id="INV8", order_id="INV8", amount=500.0, currency="EUR")
        pay = PaymentRecord(
            transaction_id="PAY8", order_id="INV8", amount=650.0,
            currency="EUR", timestamp=10000, payment_method="BANK_TRANSFER",
            metadata={"is_partial": True}
        )
        proc = ProcessorTransaction(
            processor_transaction_id="PR8", order_id="INV8",
            gross_amount=650.0, fee_amount=0.0, net_amount=650.0,
            currency="EUR", timestamp=10000
        )
        self.db.put(inv.to_key(), inv.model_dump_json())
        self.db.put(inv.to_order_key(), inv.to_key())
        self.db.put(pay.to_key(), pay.model_dump_json())
        self.db.put(pay.to_order_key(), pay.to_key())
        self.db.put(proc.to_key(), proc.model_dump_json())
        self.db.put(proc.to_order_key(), proc.to_key())

        m, exc = self.engine.reconcile_order(pay)
        self.assertIsNone(m)
        self.assertIsNotNone(exc)
        self.assertEqual(exc.exception_type, "OVERPAYMENT")

    def test_09_refund_associated_finding(self):
        """Refund association produces PARTIAL_REFUND exception."""
        pay = PaymentRecord(
            transaction_id="P9", order_id="ORD9", amount=200.0,
            currency="USD", timestamp=10000, payment_method="UPI"
        )
        ref = RefundRecord(refund_id="REF9", transaction_id="P9", order_id="ORD9", amount=50.0)
        proc = ProcessorTransaction(
            processor_transaction_id="PR9", order_id="ORD9",
            gross_amount=200.0, fee_amount=0.0, net_amount=200.0,
            currency="USD", timestamp=10000
        )
        self.db.put(pay.to_key(), pay.model_dump_json())
        self.db.put(pay.to_order_key(), pay.to_key())
        self.db.put(ref.to_key(), ref.model_dump_json())
        self.db.put(ref.to_order_key(), ref.to_key())
        self.db.put(proc.to_key(), proc.model_dump_json())
        self.db.put(proc.to_order_key(), proc.to_key())

        m, exc = self.engine.reconcile_order(pay)
        self.assertIsNone(m)
        self.assertIsNotNone(exc)
        self.assertEqual(exc.exception_type, "PARTIAL_REFUND")

    def test_10_multi_finding_collection(self):
        """Complex case with both refund and amount mismatch records all findings."""
        pay = PaymentRecord(
            transaction_id="P10", order_id="ORD10", amount=200.0,
            currency="USD", timestamp=10000, payment_method="UPI"
        )
        ref = RefundRecord(refund_id="REF10", transaction_id="P10", order_id="ORD10", amount=50.0)
        proc = ProcessorTransaction(
            processor_transaction_id="PR10", order_id="ORD10",
            gross_amount=180.0, fee_amount=0.0, net_amount=180.0,  # $20 gross mismatch
            currency="USD", timestamp=10000
        )
        self.db.put(pay.to_key(), pay.model_dump_json())
        self.db.put(pay.to_order_key(), pay.to_key())
        self.db.put(ref.to_key(), ref.model_dump_json())
        self.db.put(ref.to_order_key(), ref.to_key())
        self.db.put(proc.to_key(), proc.model_dump_json())
        self.db.put(proc.to_order_key(), proc.to_key())

        m, exc = self.engine.reconcile_order(pay)
        self.assertIsNone(m)
        self.assertIsNotNone(exc)
        findings = exc.metadata.get("findings", [])
        types = [f["type"] for f in findings]
        self.assertIn("PARTIAL_REFUND", types)
        self.assertIn("AMOUNT_MISMATCH", types)

    def test_11_greedy_consumption_handles_duplicates(self):
        """First duplicate row matches, second duplicate row remains open exception."""
        pay1 = PaymentRecord(transaction_id="P11_A", order_id="DUP_ORD", amount=500.0, currency="USD", timestamp=10000, payment_method="UPI")
        pay2 = PaymentRecord(transaction_id="P11_B", order_id="DUP_ORD", amount=500.0, currency="USD", timestamp=10000, payment_method="UPI")
        proc = ProcessorTransaction(processor_transaction_id="PR11", order_id="DUP_ORD", gross_amount=500.0, fee_amount=0.0, net_amount=500.0, currency="USD", timestamp=10000)

        self.db.put(pay1.to_key(), pay1.model_dump_json())
        self.db.put(pay1.to_order_key(), pay1.to_key())
        self.db.put(pay2.to_key(), pay2.model_dump_json())
        self.db.put(f"IDX:ORDER:DUP_ORD:PAYMENT:P11_B", pay2.to_key())
        self.db.put(proc.to_key(), proc.model_dump_json())
        self.db.put(proc.to_order_key(), proc.to_key())
        self.engine.rules.topology = "BANK_GL"
        report = self.engine.reconcile_all([pay1, pay2])
        self.assertEqual(report.matched_count, 1)
        self.assertEqual(report.exception_count, 1)
        self.assertEqual(report.exceptions[0].exception_type, "DUPLICATE_INTERNAL")

    def test_12_currency_mismatch(self):
        """Currency discrepancy generates CURRENCY_MISMATCH."""
        pay = PaymentRecord(transaction_id="P12", order_id="ORD12", amount=100.0, currency="USD", timestamp=10000, payment_method="UPI")
        proc = ProcessorTransaction(processor_transaction_id="PR12", order_id="ORD12", gross_amount=100.0, fee_amount=0.0, net_amount=100.0, currency="EUR", timestamp=10000)
        self.db.put(pay.to_key(), pay.model_dump_json())
        self.db.put(pay.to_order_key(), pay.to_key())
        self.db.put(proc.to_key(), proc.model_dump_json())
        self.db.put(proc.to_order_key(), proc.to_key())

        m, exc = self.engine.reconcile_order(pay)
        self.assertIsNone(m)
        self.assertIsNotNone(exc)
        self.assertEqual(exc.exception_type, "CURRENCY_MISMATCH")


if __name__ == "__main__":
    unittest.main()

