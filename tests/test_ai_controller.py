"""
Unit tests for AI Controller Agent, tool execution, and verification guardrails.
"""

import shutil
import unittest
import json
from recon.storage import MiniVaultDBClient
from recon.exceptions import FinancialException
from ai.agent import AIController
from ai.llm import BaseLLMProvider, MockLLMProvider
from ingestion.schemas import PaymentRecord, SettlementRecord


class FakeHallucinatingLLM(BaseLLMProvider):
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        return json.dumps({
            "decision": "RESOLVED",
            "confidence": 0.99,
            "reason": "I resolved this by citing a fake transaction ID.",
            "evidence": ["TXN_NON_EXISTENT_999999"],
            "recommended_action": "mark_reconciled",
        })


class TestAIController(unittest.TestCase):
    def setUp(self):
        self.test_dir = "./testdb_ai_unit"
        shutil.rmtree(self.test_dir, ignore_errors=True)
        self.db = MiniVaultDBClient(db_dir=self.test_dir, memtable_bytes=4 * 1024 * 1024)

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_fee_discrepancy_resolution(self):
        # Store payment and settlement with international card tier
        pay = PaymentRecord(
            merchant_id="MERCH_01",
            transaction_id="TXN_20001",
            order_id="ORD_10001",
            customer_id="CUST_1234",
            amount=1000.0,
            payment_method="CREDIT_CARD",
            timestamp=1714500000,
            metadata={"card_tier": "INTERNATIONAL_PREMIUM"},
        )
        settle = SettlementRecord(
            merchant_id="MERCH_01",
            settlement_id="SET_40001",
            transaction_id="TXN_20001",
            gross_amount=1000.0,
            fees=35.0,  # 3.5%
            net_amount=965.0,
            timestamp=1714586400,
            metadata={"fee_code": "INTL_CARD_SURCHARGE_3.5%"},
        )
        self.db.put_record(pay)
        self.db.put_record(settle)

        exc = FinancialException(
            exception_id="EXC_TEST_01",
            merchant_id="MERCH_01",
            exception_type="FEE_DISCREPANCY",
            primary_record_type="SETTLEMENT",
            primary_record_id="SET_40001",
            related_record_ids=["TXN_20001"],
            expected_value=980.0,  # Standard 2% fee
            actual_value=965.0,   # Actual 3.5% fee
            difference=15.0,
            candidate_records=[pay.model_dump(), settle.model_dump()],
        )

        controller = AIController(self.db, llm_provider=MockLLMProvider())
        result = controller.investigate(exc)

        self.assertIn(result.decision, ("RESOLVED", "AI_RESOLVED"))
        self.assertEqual(exc.status, "AI_RESOLVED")
        self.assertTrue(len(result.evidence_ids) > 0)
        self.assertTrue(result.verification_passed)
        self.assertGreaterEqual(len(exc.audit_trail), 2)

    def test_amount_mismatch_human_review_escalation(self):
        exc = FinancialException(
            exception_id="EXC_TEST_02",
            merchant_id="MERCH_01",
            exception_type="AMOUNT_MISMATCH",
            primary_record_type="PAYMENT",
            primary_record_id="TXN_20002",
            expected_value=1200.0,
            actual_value=1000.0,
            difference=200.0,
        )

        controller = AIController(self.db, llm_provider=MockLLMProvider())
        result = controller.investigate(exc)

        self.assertEqual(result.decision, "HUMAN_REVIEW")
        self.assertEqual(exc.status, "HUMAN_REVIEW")

    def test_hallucination_guardrail_rejection(self):
        # Test that citing a fake non-existent ID fails verification and routes to HUMAN_REVIEW
        exc = FinancialException(
            exception_id="EXC_TEST_03",
            merchant_id="MERCH_01",
            exception_type="FEE_DISCREPANCY",
            primary_record_type="SETTLEMENT",
            primary_record_id="SET_40003",
            expected_value=980.0,
            actual_value=965.0,
            difference=15.0,
        )

        controller = AIController(self.db, llm_provider=FakeHallucinatingLLM())
        result = controller.investigate(exc)

        # Verification must fail and override to HUMAN_REVIEW
        self.assertFalse(result.verification_passed)
        self.assertEqual(result.decision, "HUMAN_REVIEW")
        self.assertEqual(exc.status, "HUMAN_REVIEW")
        self.assertIn("UNVERIFIED_EVIDENCE", result.reason)


if __name__ == "__main__":
    unittest.main()

