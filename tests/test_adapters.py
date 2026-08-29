"""
Unit Tests for Source Adapters and Configurable Fee Policies.
"""

import unittest
from ingestion.schemas import FeePolicy, PaymentRecord, ProcessorTransaction, SettlementBatch
from recon.rules import FeePolicyRegistry, ReconciliationRules
from ingestion.adapters.reconriver import ReconRiverAdapter
from ingestion.adapters.razorpay import RazorpayStyleSyntheticAdapter
from ingestion.adapters.generic_csv import GenericCSVAdapter


class TestFeePolicyAndAdapters(unittest.TestCase):
    def test_fee_policy_financial_rounding(self):
        # ReconRiver formula: 2.9% + 0.30 with HALF_UP rounding
        policy = FeePolicy(
            policy_id="RECONRIVER_TEST",
            percentage_rate=2.90,
            fixed_charge=0.30,
        )
        # $895.00 * 0.029 + 0.30 = 25.955 + 0.30 = 26.255 -> 26.26
        fee = policy.calculate_fee(895.00)
        self.assertEqual(fee, 26.26)
        self.assertEqual(policy.calculate_net(895.00), 868.74)

        # Zero fee UPI policy
        upi_policy = FeePolicy(policy_id="UPI_TEST", percentage_rate=0.0, fixed_charge=0.0)
        self.assertEqual(upi_policy.calculate_fee(1500.00), 0.0)
        self.assertEqual(upi_policy.calculate_net(1500.00), 1500.00)

    def test_fee_policy_registry_hierarchy(self):
        registry = FeePolicyRegistry()
        policy = registry.match_policy(currency="USD", payment_method="CARD_SYNTHETIC")
        self.assertEqual(policy.percentage_rate, 2.90)
        self.assertEqual(policy.fixed_charge, 0.30)

        inr_card = registry.match_policy(currency="INR", payment_method="CREDIT_CARD")
        self.assertEqual(inr_card.percentage_rate, 2.0)
        self.assertEqual(inr_card.fixed_charge, 0.0)

    def test_razorpay_adapter_generation(self):
        adapter = RazorpayStyleSyntheticAdapter(count=50, seed=42)
        dataset = adapter.load_dataset()
        self.assertEqual(len(dataset.payments), 50)
        self.assertGreater(len(dataset.batches), 0)
        self.assertGreater(len(dataset.bank_transactions), 0)
        self.assertEqual(len(dataset.ground_truth), 50 + len(dataset.batches))


if __name__ == "__main__":
    unittest.main()

