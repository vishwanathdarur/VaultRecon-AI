"""
Synthetic Financial Record Generator with Ground Truth Labels.
Generates multi-source datasets:
- Payments
- Invoices
- Settlements
- Bank Transactions
- Refunds
Includes standard clean matches and intentional edge cases with known ground truth.
"""

import random
import time
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, field

from ingestion.schemas import (
    PaymentRecord,
    InvoiceRecord,
    SettlementRecord,
    BankTransactionRecord,
    RefundRecord,
)


@dataclass
class GroundTruthCase:
    case_id: str
    scenario_type: str  # EXACT_MATCH, FEE_ANOMALY, NOISY_BANK_REF, AMOUNT_MISMATCH, MISSING_SETTLEMENT, REFUND_NETTING, DUPLICATE_PAYMENT
    expected_decision: str  # MATCHED, AI_RESOLVED, HUMAN_REVIEW
    expected_reason: str
    primary_record_ids: List[str]
    supporting_evidence_ids: List[str] = field(default_factory=list)


@dataclass
class GeneratedDataset:
    payments: List[PaymentRecord]
    invoices: List[InvoiceRecord]
    settlements: List[SettlementRecord]
    bank_transactions: List[BankTransactionRecord]
    refunds: List[RefundRecord]
    ground_truth: List[GroundTruthCase]


# Standard fee schedules
STANDARD_FEES = {
    "UPI": 0.0,
    "DEBIT_CARD": 0.009,  # 0.9%
    "CREDIT_CARD": 0.02,  # 2.0%
    "NET_BANKING": 15.0,  # Flat 15
}


def calculate_standard_fee(payment_method: str, amount: float) -> float:
    if payment_method == "UPI":
        return 0.0
    elif payment_method == "CREDIT_CARD":
        return round(amount * 0.02, 2)
    elif payment_method == "DEBIT_CARD":
        return round(amount * 0.009, 2)
    elif payment_method == "NET_BANKING":
        return 15.0
    return round(amount * 0.015, 2)


class SyntheticDataGenerator:
    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = random.Random(seed)
        self.base_time = 1714500000  # Fixed baseline unix timestamp

    def generate(self, count: int = 100, scenario_override: Optional[str] = None) -> GeneratedDataset:
        """
        Generate `count` financial lifecycle cases across all tables.
        """
        payments: List[PaymentRecord] = []
        invoices: List[InvoiceRecord] = []
        settlements: List[SettlementRecord] = []
        bank_txns: List[BankTransactionRecord] = []
        refunds: List[RefundRecord] = []
        ground_truth: List[GroundTruthCase] = []

        merchants = [f"MERCH_{i:02d}" for i in range(1, 6)]
        payment_methods = ["UPI", "CREDIT_CARD", "DEBIT_CARD", "NET_BANKING"]

        for i in range(1, count + 1):
            merchant = self.rng.choice(merchants)
            cust_id = f"CUST_{self.rng.randint(1000, 9999)}"
            order_id = f"ORD_{10000 + i}"
            txn_id = f"TXN_{20000 + i}"
            inv_id = f"INV_{30000 + i}"
            set_id = f"SET_{40000 + i}"
            bnk_id = f"BNK_{50000 + i}"
            ref_id = f"REF_{60000 + i}"

            base_amount = round(self.rng.uniform(100.0, 5000.0), 2)
            method = self.rng.choice(payment_methods)
            t0 = self.base_time + (i * 300)

            # Determine scenario
            if scenario_override:
                scenario = scenario_override.upper()
            else:
                rand_val = self.rng.random()
                if rand_val < 0.70:
                    scenario = "EXACT_MATCH"
                elif rand_val < 0.80:
                    scenario = "FEE_ANOMALY"
                elif rand_val < 0.90:
                    scenario = "NOISY_BANK_REF"
                elif rand_val < 0.95:
                    scenario = "AMOUNT_MISMATCH"
                else:
                    scenario = "MISSING_SETTLEMENT"

            if scenario == "EXACT_MATCH":
                # 1. EXACT / STANDARD MATCH
                inv = InvoiceRecord(
                    merchant_id=merchant,
                    invoice_id=inv_id,
                    order_id=order_id,
                    customer_id=cust_id,
                    amount=base_amount,
                    timestamp=t0,
                    status="PAID",
                )
                pay = PaymentRecord(
                    merchant_id=merchant,
                    transaction_id=txn_id,
                    order_id=order_id,
                    customer_id=cust_id,
                    amount=base_amount,
                    payment_method=method,
                    timestamp=t0 + 120,
                    status="SUCCESS",
                )
                std_fee = calculate_standard_fee(method, base_amount)
                net_amt = round(base_amount - std_fee, 2)

                settle = SettlementRecord(
                    merchant_id=merchant,
                    settlement_id=set_id,
                    transaction_id=txn_id,
                    gross_amount=base_amount,
                    fees=std_fee,
                    net_amount=net_amt,
                    timestamp=t0 + 86400,
                    status="SETTLED",
                )
                bank = BankTransactionRecord(
                    merchant_id=merchant,
                    bank_transaction_id=bnk_id,
                    reference=set_id,
                    amount=net_amt,
                    transaction_type="CREDIT",
                    description=f"ACH CREDIT / {set_id} / {merchant}",
                    timestamp=t0 + 86400 + 3600,
                )

                invoices.append(inv)
                payments.append(pay)
                settlements.append(settle)
                bank_txns.append(bank)

                ground_truth.append(GroundTruthCase(
                    case_id=f"CASE_{i:04d}",
                    scenario_type="EXACT_MATCH",
                    expected_decision="MATCHED",
                    expected_reason="Exact match on order ID, payment amount, standard fee, and bank reference.",
                    primary_record_ids=[pay.transaction_id, inv.invoice_id, settle.settlement_id, bank.bank_transaction_id],
                ))

            elif scenario == "FEE_ANOMALY":
                # 2. FEE ANOMALY (AI RESOLVABLE)
                # Merchant has a special contractual surcharge (e.g. International Card 3.5% or Priority Settlement fee 1.5%)
                inv = InvoiceRecord(
                    merchant_id=merchant,
                    invoice_id=inv_id,
                    order_id=order_id,
                    customer_id=cust_id,
                    amount=base_amount,
                    timestamp=t0,
                )
                pay = PaymentRecord(
                    merchant_id=merchant,
                    transaction_id=txn_id,
                    order_id=order_id,
                    customer_id=cust_id,
                    amount=base_amount,
                    payment_method="CREDIT_CARD",
                    timestamp=t0 + 120,
                    metadata={"card_tier": "INTERNATIONAL_PREMIUM"},
                )
                contract_fee = round(base_amount * 0.035, 2)  # 3.5% contractual rate
                net_amt = round(base_amount - contract_fee, 2)

                settle = SettlementRecord(
                    merchant_id=merchant,
                    settlement_id=set_id,
                    transaction_id=txn_id,
                    gross_amount=base_amount,
                    fees=contract_fee,
                    net_amount=net_amt,
                    timestamp=t0 + 86400,
                    metadata={"fee_code": "INTL_CARD_SURCHARGE_3.5%"},
                )
                bank = BankTransactionRecord(
                    merchant_id=merchant,
                    bank_transaction_id=bnk_id,
                    reference=set_id,
                    amount=net_amt,
                    transaction_type="CREDIT",
                    description=f"PAYOUT {set_id} {merchant}",
                    timestamp=t0 + 86400 + 3600,
                )

                invoices.append(inv)
                payments.append(pay)
                settlements.append(settle)
                bank_txns.append(bank)

                ground_truth.append(GroundTruthCase(
                    case_id=f"CASE_{i:04d}",
                    scenario_type="FEE_ANOMALY",
                    expected_decision="AI_RESOLVED",
                    expected_reason="Difference in settlement fee is verified by contractual international card surcharge rule of 3.5%.",
                    primary_record_ids=[pay.transaction_id, settle.settlement_id],
                    supporting_evidence_ids=["RULE_INTL_CARD_3.5", settle.settlement_id],
                ))

            elif scenario == "NOISY_BANK_REF":
                # 3. NOISY BANK REFERENCE / TRUNCATED DESCRIPTION (AI RESOLVABLE)
                inv = InvoiceRecord(
                    merchant_id=merchant,
                    invoice_id=inv_id,
                    order_id=order_id,
                    customer_id=cust_id,
                    amount=base_amount,
                    timestamp=t0,
                )
                pay = PaymentRecord(
                    merchant_id=merchant,
                    transaction_id=txn_id,
                    order_id=order_id,
                    customer_id=cust_id,
                    amount=base_amount,
                    payment_method="UPI",
                    timestamp=t0 + 60,
                )
                std_fee = 0.0
                net_amt = base_amount

                settle = SettlementRecord(
                    merchant_id=merchant,
                    settlement_id=set_id,
                    transaction_id=txn_id,
                    gross_amount=base_amount,
                    fees=std_fee,
                    net_amount=net_amt,
                    timestamp=t0 + 86400,
                )
                # Truncated or mangled reference in bank narrative:
                mangled_ref = f"UPI/CR/{txn_id[-4:]}/PAYMENT-ORD"
                bank = BankTransactionRecord(
                    merchant_id=merchant,
                    bank_transaction_id=bnk_id,
                    reference=mangled_ref,
                    amount=net_amt,
                    transaction_type="CREDIT",
                    description=f"CMS-NEFT-INW/{mangled_ref}/{set_id[-5:]}",
                    timestamp=t0 + 86400 + 1800,
                )

                invoices.append(inv)
                payments.append(pay)
                settlements.append(settle)
                bank_txns.append(bank)

                ground_truth.append(GroundTruthCase(
                    case_id=f"CASE_{i:04d}",
                    scenario_type="NOISY_BANK_REF",
                    expected_decision="AI_RESOLVED",
                    expected_reason="Bank deposit amount and temporal window match settlement, narrative contains sub-string reference.",
                    primary_record_ids=[settle.settlement_id, bank.bank_transaction_id],
                    supporting_evidence_ids=[settle.settlement_id, bank.bank_transaction_id],
                ))

            elif scenario == "AMOUNT_MISMATCH":
                # 4. AMOUNT MISMATCH / FRAUD / DISCREPANCY (UNRESOLVED -> HUMAN REVIEW)
                # Payment was $500, but Invoice was $650, no refund or discount documented
                inv = InvoiceRecord(
                    merchant_id=merchant,
                    invoice_id=inv_id,
                    order_id=order_id,
                    customer_id=cust_id,
                    amount=base_amount + 150.0,  # Unexplained discrepancy
                    timestamp=t0,
                )
                pay = PaymentRecord(
                    merchant_id=merchant,
                    transaction_id=txn_id,
                    order_id=order_id,
                    customer_id=cust_id,
                    amount=base_amount,
                    payment_method=method,
                    timestamp=t0 + 60,
                )
                std_fee = calculate_standard_fee(method, base_amount)
                net_amt = round(base_amount - std_fee, 2)

                settle = SettlementRecord(
                    merchant_id=merchant,
                    settlement_id=set_id,
                    transaction_id=txn_id,
                    gross_amount=base_amount,
                    fees=std_fee,
                    net_amount=net_amt,
                    timestamp=t0 + 86400,
                )

                invoices.append(inv)
                payments.append(pay)
                settlements.append(settle)

                ground_truth.append(GroundTruthCase(
                    case_id=f"CASE_{i:04d}",
                    scenario_type="AMOUNT_MISMATCH",
                    expected_decision="HUMAN_REVIEW",
                    expected_reason="Payment amount is underpaid compared to invoice with no adjustment or partial record.",
                    primary_record_ids=[pay.transaction_id, inv.invoice_id],
                ))

            else:
                # 5. MISSING COUNTERPARTY / UNRECONCILED (HUMAN REVIEW)
                # Payment recorded but settlement completely missing from gateway
                inv = InvoiceRecord(
                    merchant_id=merchant,
                    invoice_id=inv_id,
                    order_id=order_id,
                    customer_id=cust_id,
                    amount=base_amount,
                    timestamp=t0,
                )
                pay = PaymentRecord(
                    merchant_id=merchant,
                    transaction_id=txn_id,
                    order_id=order_id,
                    customer_id=cust_id,
                    amount=base_amount,
                    payment_method=method,
                    timestamp=t0 + 60,
                )
                invoices.append(inv)
                payments.append(pay)

                ground_truth.append(GroundTruthCase(
                    case_id=f"CASE_{i:04d}",
                    scenario_type="MISSING_SETTLEMENT",
                    expected_decision="HUMAN_REVIEW",
                    expected_reason="Payment received but missing corresponding gateway settlement record beyond SLA.",
                    primary_record_ids=[pay.transaction_id],
                ))

        return GeneratedDataset(
            payments=payments,
            invoices=invoices,
            settlements=settlements,
            bank_transactions=bank_txns,
            refunds=refunds,
            ground_truth=ground_truth,
        )
