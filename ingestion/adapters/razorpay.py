"""
Razorpay-Style Synthetic Dataset Adapter for Track 4 Multi-Source Reconciliation.
Generates multi-topology financial datasets (1:1, 1:Many, Batch Many:1, and realistic exceptions).
"""

import time
import random
import uuid
from typing import Dict, Any, List, Optional
from collections import defaultdict

from ingestion.adapters.base import BaseSourceAdapter, NormalizedDataset
from ingestion.schemas import (
    PaymentRecord,
    InvoiceRecord,
    ProcessorTransaction,
    SettlementBatch,
    BankTransactionRecord,
    RefundRecord,
    FeePolicy,
)


class RazorpayStyleSyntheticAdapter(BaseSourceAdapter):
    def __init__(
        self,
        count: int = 100,
        seed: int = 42,
        batch_size: int = 10,
        exception_rate: float = 0.20,
    ):
        super().__init__(source_name="RazorpayTrack4Synthetic")
        self.count = count
        self.seed = seed
        self.batch_size = batch_size
        self.exception_rate = exception_rate

    def load_dataset(self) -> NormalizedDataset:
        random.seed(self.seed)
        dataset = NormalizedDataset(source_name=self.source_name)

        # Standard Policies
        dataset.fee_policies.extend([
            FeePolicy(policy_id="UPI_STD", name="UPI Standard", percentage_rate=0.0, fixed_charge=0.0, payment_method="UPI", currency="INR"),
            FeePolicy(policy_id="CARD_STD", name="Card Standard", percentage_rate=2.0, fixed_charge=0.0, payment_method="CREDIT_CARD", currency="INR"),
            FeePolicy(policy_id="DEBIT_STD", name="Debit Standard", percentage_rate=0.9, fixed_charge=0.0, payment_method="DEBIT_CARD", currency="INR"),
            FeePolicy(policy_id="NB_STD", name="NetBanking Standard", percentage_rate=0.0, fixed_charge=15.0, payment_method="NET_BANKING", currency="INR"),
        ])

        base_ts = 1714500000
        payment_methods = ["UPI", "CREDIT_CARD", "DEBIT_CARD", "NET_BANKING"]

        batch_groups = defaultdict(list)

        for i in range(1, self.count + 1):
            ts = base_ts + (i * 300)
            order_id = f"ORD_{10000 + i}"
            pay_id = f"TXN_{20000 + i}"
            inv_id = f"INV_{30000 + i}"
            proc_id = f"PROC_{40000 + i}"
            cust_id = f"CUST_{random.randint(100, 999)}"
            method = random.choice(payment_methods)
            gross = round(random.uniform(100.0, 5000.0), 2)
            merchant_id = f"MERCH_{random.randint(1, 5):02d}"

            batch_idx = (i - 1) // self.batch_size + 1
            batch_id = f"BATCH_RZP_{batch_idx:04d}"

            # Injected scenario
            is_exception = (i % int(1.0 / max(self.exception_rate, 0.01))) == 0
            exc_scenario = "CLEAN"
            if is_exception:
                exc_types = ["FEE_MISMATCH", "MISSING_PROCESSOR", "AMOUNT_MISMATCH", "REFUND", "NOISY_BANK"]
                exc_scenario = exc_types[i % len(exc_types)]

            # 1. Payment Record
            pay = PaymentRecord(
                merchant_id=merchant_id,
                transaction_id=pay_id,
                order_id=order_id,
                customer_id=cust_id,
                amount=gross,
                currency="INR",
                payment_method=method,
                timestamp=ts,
                status="SUCCESS",
                source="RazorpayAdapter:Payment",
            )
            dataset.payments.append(pay)

            # 2. Invoice Record
            inv_gross = gross if exc_scenario != "AMOUNT_MISMATCH" else round(gross + 50.0, 2)
            inv = InvoiceRecord(
                merchant_id=merchant_id,
                invoice_id=inv_id,
                order_id=order_id,
                customer_id=cust_id,
                amount=inv_gross,
                currency="INR",
                timestamp=ts,
                status="PAID",
                source="RazorpayAdapter:Invoice",
            )
            dataset.invoices.append(inv)

            # 3. Processor Transaction
            if exc_scenario == "MISSING_PROCESSOR":
                gt_outcome = "MISSING_PROCESSOR"
            elif exc_scenario == "REFUND":
                ref = RefundRecord(
                    merchant_id=merchant_id,
                    refund_id=f"REF_{50000 + i}",
                    transaction_id=pay_id,
                    order_id=order_id,
                    amount=gross,
                    currency="INR",
                    timestamp=ts + 3600,
                    reason="CUSTOMER_RETURN",
                    status="PROCESSED",
                    source="RazorpayAdapter:Refund",
                )
                dataset.refunds.append(ref)
                gt_outcome = "FULL_REFUND"
            else:
                # Calculate standard fee
                if method == "UPI":
                    fee = 0.0
                elif method == "CREDIT_CARD":
                    fee = round(gross * 0.02, 2)
                elif method == "DEBIT_CARD":
                    fee = round(gross * 0.009, 2)
                else:
                    fee = 15.0

                if exc_scenario == "FEE_MISMATCH":
                    fee = round(fee + 25.0, 2)
                    gt_outcome = "FEE_MISMATCH"
                elif exc_scenario == "AMOUNT_MISMATCH":
                    gt_outcome = "AMOUNT_MISMATCH"
                else:
                    gt_outcome = "MATCHED"

                net = round(gross - fee, 2)
                proc_txn = ProcessorTransaction(
                    merchant_id=merchant_id,
                    processor_transaction_id=proc_id,
                    order_id=order_id,
                    processor_name="RAZORPAY",
                    event_type="CAPTURE",
                    gross_amount=gross,
                    fee_amount=fee,
                    net_amount=net,
                    currency="INR",
                    settlement_batch_id=batch_id,
                    timestamp=ts + 60,
                    status="SETTLED",
                    source="RazorpayAdapter:Processor",
                )
                dataset.processor_transactions.append(proc_txn)
                batch_groups[batch_id].append(proc_txn)

            # Ground truth record
            dataset.ground_truth.append({
                "work_key": order_id,
                "internal_payment_id": pay_id,
                "processor_transaction_id": proc_id if exc_scenario != "MISSING_PROCESSOR" else None,
                "expected_outcome": gt_outcome,
                "scenario": exc_scenario,
                "result_scope": "ORDER",
            })

        # 4. Create Settlement Batches and Bank Transactions
        for b_id, txns in batch_groups.items():
            tot_gross = round(sum(t.gross_amount for t in txns), 2)
            tot_fees = round(sum(t.fee_amount for t in txns), 2)
            tot_net = round(sum(t.net_amount for t in txns), 2)
            b_ts = min(t.timestamp for t in txns) if txns else base_ts

            batch = SettlementBatch(
                merchant_id="MERCH_01",
                batch_id=b_id,
                processor_name="RAZORPAY",
                total_gross=tot_gross,
                total_fees=tot_fees,
                total_net=tot_net,
                currency="INR",
                transaction_count=len(txns),
                transaction_ids=[t.processor_transaction_id for t in txns],
                timestamp=b_ts,
                status="CLOSED",
                source="RazorpayAdapter:Batch",
            )
            dataset.batches.append(batch)

            # Bank deposit payout
            bank_id = f"BANK_{b_id}"
            bank_txn = BankTransactionRecord(
                merchant_id="MERCH_01",
                bank_transaction_id=bank_id,
                reference=b_id,
                amount=tot_net,
                currency="INR",
                timestamp=b_ts + 86400,
                transaction_type="CREDIT",
                description=f"Razorpay Payout for {b_id} (Ref: {b_id})",
                source="RazorpayAdapter:Bank",
            )
            dataset.bank_transactions.append(bank_txn)

            dataset.ground_truth.append({
                "work_key": b_id,
                "settlement_batch_id": b_id,
                "bank_entry_id": bank_id,
                "expected_outcome": "MATCHED",
                "result_scope": "SETTLEMENT",
            })

        return dataset

