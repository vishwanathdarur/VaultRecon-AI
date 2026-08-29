"""
Unit Tests for Source Adapters and Configurable Fee Policies.
"""

import unittest
import tempfile
import os
import csv
from ingestion.schemas import FeePolicy, PaymentRecord, ProcessorTransaction
from recon.rules import FeePolicyRegistry
from ingestion.adapters.generic_csv import GenericCSVAdapter


class TestFeePolicyAndAdapters(unittest.TestCase):
    def test_fee_policy_financial_rounding(self):
        policy = FeePolicy(
            policy_id="STANDARD_CARD_TEST",
            percentage_rate=2.90,
            fixed_charge=0.30,
        )
        # $895.00 * 0.029 + 0.30 = 25.955 + 0.30 = 26.255 -> 26.26
        fee = policy.calculate_fee(895.00)
        self.assertEqual(fee, 26.26)
        self.assertEqual(policy.calculate_net(895.00), 868.74)

        # Zero fee policy
        zero_policy = FeePolicy(policy_id="ZERO_TEST", percentage_rate=0.0, fixed_charge=0.0)
        self.assertEqual(zero_policy.calculate_fee(1500.00), 0.0)
        self.assertEqual(zero_policy.calculate_net(1500.00), 1500.00)

    def test_fee_policy_registry_hierarchy(self):
        registry = FeePolicyRegistry()
        policy = registry.match_policy(currency="USD", payment_method="CARD")
        self.assertEqual(policy.percentage_rate, 2.90)
        self.assertEqual(policy.fixed_charge, 0.30)

        inr_card = registry.match_policy(currency="INR", payment_method="CREDIT_CARD")
        self.assertEqual(inr_card.percentage_rate, 2.0)
        self.assertEqual(inr_card.fixed_charge, 0.0)

    def test_generic_csv_adapter(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(["tx_id", "ref_order", "gross_val", "curr", "time_epoch"])
            writer.writerow(["TX_1001", "ORD_5001", "250.00", "USD", "1700000000"])
            temp_csv = f.name

        try:
            adapter = GenericCSVAdapter(
                file_path=temp_csv,
                record_type="PAYMENT",
                column_mapping={
                    "transaction_id": "tx_id",
                    "order_id": "ref_order",
                    "amount": "gross_val",
                    "currency": "curr",
                    "timestamp": "time_epoch",
                },
            )
            dataset = adapter.load_dataset()
            self.assertEqual(len(dataset.payments), 1)
            self.assertEqual(dataset.payments[0].transaction_id, "TX_1001")
            self.assertEqual(dataset.payments[0].order_id, "ORD_5001")
            self.assertEqual(dataset.payments[0].amount, 250.00)
        finally:
            if os.path.exists(temp_csv):
                os.remove(temp_csv)


if __name__ == "__main__":
    unittest.main()

