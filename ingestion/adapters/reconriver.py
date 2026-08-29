"""
ReconRiver Source Adapter for VaultRecon AI.
Converts ReconRiver synthetic datasets (clean-settlement, mixed-exceptions, month-end-close, failure-recovery)
into normalized financial records with duplicate tracking and batch aggregation.
"""

import os
import csv
from datetime import datetime
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


def parse_iso_timestamp(iso_str: str) -> int:
    """Convert ISO-8601 string (e.g. 2026-01-01T02:27:44Z) to integer unix timestamp."""
    if not iso_str:
        return 0
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except Exception:
        return 0


class ReconRiverAdapter(BaseSourceAdapter):
    def __init__(self, dataset_dir: str):
        super().__init__(source_name="ReconRiver")
        self.dataset_dir = dataset_dir

    def load_dataset(self) -> NormalizedDataset:
        dataset = NormalizedDataset(source_name="ReconRiver")

        # 1. Configured Fee Policy for ReconRiver (2.90% + $0.30)
        fee_policy = FeePolicy(
            policy_id="RECONRIVER_STANDARD",
            name="ReconRiver Standard Policy (2.9% + $0.30)",
            percentage_rate=2.90,
            fixed_charge=0.30,
            currency="USD",
            processor="RECONRIVER",
        )
        dataset.fee_policies.append(fee_policy)

        # File paths
        internal_file = os.path.join(self.dataset_dir, "internal_transactions.csv")
        processor_file = os.path.join(self.dataset_dir, "processor_transactions.csv")
        bank_file = os.path.join(self.dataset_dir, "bank_settlements.csv")
        expected_file = os.path.join(self.dataset_dir, "expected_reconciliation.csv")

        seen_internal_ids = set()
        seen_processor_ids = set()
        batch_txns = defaultdict(list)

        # 1. Parse internal_transactions.csv
        if os.path.exists(internal_file):
            with open(internal_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row_idx, row in enumerate(reader, start=2):
                    try:
                        ts = parse_iso_timestamp(row["occurred_at"])
                        gross = float(row["gross_amount"])
                        order_id = row["merchant_order_id"]
                        pay_id = row["internal_payment_id"]
                        cust_ref = row.get("synthetic_customer_reference", "UNKNOWN")
                        method = row.get("payment_method", "CARD_SYNTHETIC")
                        curr = row.get("currency", "USD")
                        status = row.get("payment_status", "CAPTURED")

                        is_dup = pay_id in seen_internal_ids
                        seen_internal_ids.add(pay_id)

                        pay = PaymentRecord(
                            merchant_id="RECONRIVER_MERCHANT",
                            transaction_id=pay_id if not is_dup else f"{pay_id}_DUP_{row_idx}",
                            order_id=order_id,
                            customer_id=cust_ref,
                            amount=gross,
                            currency=curr,
                            payment_method=method,
                            timestamp=ts,
                            status=status,
                            source="ReconRiver:internal_transactions",
                            metadata={
                                "internal_payment_id": pay_id,
                                "is_duplicate": is_dup,
                            },
                        )
                        dataset.payments.append(pay)

                        inv = InvoiceRecord(
                            merchant_id="RECONRIVER_MERCHANT",
                            invoice_id=f"INV_{order_id}_{row_idx}",
                            order_id=order_id,
                            customer_id=cust_ref,
                            amount=gross,
                            currency=curr,
                            timestamp=ts,
                            status="ISSUED" if status != "CAPTURED" else "PAID",
                            source="ReconRiver:internal_transactions",
                        )
                        dataset.invoices.append(inv)
                    except Exception as e:
                        dataset.schema_failures.append({
                            "file": "internal_transactions.csv",
                            "row_index": row_idx,
                            "raw_row": row,
                            "error": str(e),
                        })

        # 2. Parse processor_transactions.csv
        if os.path.exists(processor_file):
            with open(processor_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row_idx, row in enumerate(reader, start=2):
                    try:
                        ts = parse_iso_timestamp(row["processor_event_time"])
                        gross = float(row["gross_amount"])
                        fee = float(row["fee_amount"])
                        net = float(row["net_amount"])
                        proc_id = row["processor_transaction_id"]
                        order_id = row["merchant_order_id"]
                        event_type = row["processor_event_type"]
                        curr = row.get("currency", "USD")
                        batch_id = row.get("settlement_batch_id", "")
                        status = row.get("processor_status", "SETTLED")

                        is_dup_proc = proc_id in seen_processor_ids
                        seen_processor_ids.add(proc_id)

                        proc_txn = ProcessorTransaction(
                            merchant_id="RECONRIVER_MERCHANT",
                            processor_transaction_id=proc_id if not is_dup_proc else f"{proc_id}_DUP_{row_idx}",
                            order_id=order_id,
                            processor_name="RECONRIVER",
                            event_type=event_type,
                            gross_amount=gross,
                            fee_amount=fee,
                            net_amount=net,
                            currency=curr,
                            settlement_batch_id=batch_id,
                            timestamp=ts,
                            status=status,
                            source="ReconRiver:processor_transactions",
                            metadata={"is_duplicate": is_dup_proc},
                        )
                        dataset.processor_transactions.append(proc_txn)
                        if batch_id:
                            batch_txns[batch_id].append(proc_txn)

                        if event_type == "REFUND":
                            ref = RefundRecord(
                                merchant_id="RECONRIVER_MERCHANT",
                                refund_id=proc_id,
                                transaction_id=order_id,
                                order_id=order_id,
                                amount=abs(gross),
                                currency=curr,
                                timestamp=ts,
                                reason="PROCESSOR_REFUND",
                                status="PROCESSED",
                                source="ReconRiver:processor_transactions",
                            )
                            dataset.refunds.append(ref)
                    except Exception as e:
                        dataset.schema_failures.append({
                            "file": "processor_transactions.csv",
                            "row_index": row_idx,
                            "raw_row": row,
                            "error": str(e),
                        })

        # 3. Build aggregated SettlementBatch records from processor transactions
        for batch_id, txns in batch_txns.items():
            tot_gross = round(sum(t.gross_amount for t in txns), 2)
            tot_fees = round(sum(t.fee_amount for t in txns), 2)
            tot_net = round(sum(t.net_amount for t in txns), 2)
            b_curr = txns[0].currency if txns else "USD"
            b_ts = min(t.timestamp for t in txns) if txns else 0

            batch = SettlementBatch(
                merchant_id="RECONRIVER_MERCHANT",
                batch_id=batch_id,
                processor_name="RECONRIVER",
                total_gross=tot_gross,
                total_fees=tot_fees,
                total_net=tot_net,
                currency=b_curr,
                transaction_count=len(txns),
                transaction_ids=[t.processor_transaction_id for t in txns],
                timestamp=b_ts,
                status="CLOSED",
                source="ReconRiver:batch_aggregation",
            )
            dataset.batches.append(batch)

        # 4. Parse bank_settlements.csv
        seen_bank_ids = set()
        if os.path.exists(bank_file):
            with open(bank_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row_idx, row in enumerate(reader, start=2):
                    try:
                        ts = parse_iso_timestamp(row["booked_at"])
                        amt = float(row["credited_amount"])
                        bank_id = row["bank_entry_id"]
                        batch_id = row["settlement_batch_id"]
                        curr = row.get("currency", "USD")
                        ref = row.get("bank_reference", "")
                        desc = row.get("description", "")

                        is_dup_bank = bank_id in seen_bank_ids
                        seen_bank_ids.add(bank_id)

                        bank_txn = BankTransactionRecord(
                            merchant_id="RECONRIVER_MERCHANT",
                            bank_transaction_id=bank_id if not is_dup_bank else f"{bank_id}_DUP_{row_idx}",
                            reference=batch_id,
                            amount=amt,
                            currency=curr,
                            timestamp=ts,
                            transaction_type="CREDIT",
                            description=f"{desc} (Ref: {ref})",
                            source="ReconRiver:bank_settlements",
                        )
                        dataset.bank_transactions.append(bank_txn)
                    except Exception as e:
                        dataset.schema_failures.append({
                            "file": "bank_settlements.csv",
                            "row_index": row_idx,
                            "raw_row": row,
                            "error": str(e),
                        })

        # 5. Parse expected_reconciliation.csv (Ground Truth)
        if os.path.exists(expected_file):
            with open(expected_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    dataset.ground_truth.append(row)

        return dataset
