"""
Blind Test Source Adapter for VaultRecon AI.
Loads external blind test dataset directory (orders, payments, processor_transactions, bank_transactions, refunds)
into the normalized financial model.
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
    """Convert ISO-8601 string or numeric timestamp to integer unix timestamp."""
    if not iso_str:
        return 0
    try:
        if isinstance(iso_str, (int, float)):
            return int(iso_str)
        # Try numeric string
        try:
            return int(float(iso_str))
        except ValueError:
            pass
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except Exception:
        return 0


class BlindTestAdapter(BaseSourceAdapter):
    def __init__(self, dataset_dir: str):
        super().__init__(source_name="BlindTestDataset")
        self.dataset_dir = dataset_dir

    def load_dataset(self) -> NormalizedDataset:
        dataset = NormalizedDataset(source_name="BlindTestDataset")

        # Configured fee policies for Blind Test source
        dataset.fee_policies.extend([
            FeePolicy(
                policy_id="BLIND_TEST_WALLET",
                name="Blind Test Wallet Standard (1.5% + $0.10)",
                percentage_rate=1.50,
                fixed_charge=0.10,
                payment_method="WALLET",
                currency="ANY",
            ),
            FeePolicy(
                policy_id="BLIND_TEST_CARD",
                name="Blind Test Card Standard (2.9% + $0.30)",
                percentage_rate=2.90,
                fixed_charge=0.30,
                payment_method="CARD",
                currency="ANY",
            ),
            FeePolicy(
                policy_id="BLIND_TEST_UPI",
                name="Blind Test UPI Standard (0%)",
                percentage_rate=0.0,
                fixed_charge=0.0,
                payment_method="UPI",
                currency="ANY",
            ),
        ])

        orders_file = os.path.join(self.dataset_dir, "orders.csv")
        payments_file = os.path.join(self.dataset_dir, "payments.csv")
        processor_file = os.path.join(self.dataset_dir, "processor_transactions.csv")
        bank_file = os.path.join(self.dataset_dir, "bank_transactions.csv")
        refunds_file = os.path.join(self.dataset_dir, "refunds.csv")

        # 1. Parse orders.csv -> InvoiceRecord
        if os.path.exists(orders_file):
            with open(orders_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row_idx, row in enumerate(reader, start=2):
                    try:
                        inv = InvoiceRecord(
                            merchant_id=row.get("merchant_id", "MERCHANT_UNKNOWN"),
                            invoice_id=row["order_id"],
                            order_id=row["order_id"],
                            customer_id=row.get("customer_id", "CUST_UNKNOWN"),
                            amount=float(row["amount"]),
                            currency=row.get("currency", "USD"),
                            timestamp=parse_iso_timestamp(row.get("timestamp", "")),
                            status=row.get("status", "ISSUED"),
                            source="BlindTest:orders",
                        )
                        dataset.invoices.append(inv)
                    except Exception as e:
                        dataset.schema_failures.append({
                            "file": "orders.csv",
                            "row_index": row_idx,
                            "raw_row": row,
                            "error": str(e),
                        })

        # 2. Parse payments.csv -> PaymentRecord
        if os.path.exists(payments_file):
            with open(payments_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row_idx, row in enumerate(reader, start=2):
                    try:
                        pay = PaymentRecord(
                            merchant_id=row.get("merchant_id", "MERCHANT_UNKNOWN"),
                            transaction_id=row["transaction_id"],
                            order_id=row["order_id"],
                            customer_id=row.get("customer_id", "CUST_UNKNOWN"),
                            amount=float(row["amount"]),
                            currency=row.get("currency", "USD"),
                            payment_method=row.get("payment_method", "CARD"),
                            timestamp=parse_iso_timestamp(row.get("timestamp", "")),
                            status=row.get("status", "CAPTURED"),
                            source="BlindTest:payments",
                        )
                        dataset.payments.append(pay)
                    except Exception as e:
                        dataset.schema_failures.append({
                            "file": "payments.csv",
                            "row_index": row_idx,
                            "raw_row": row,
                            "error": str(e),
                        })

        # 3. Parse processor_transactions.csv -> ProcessorTransaction & aggregate Batches
        batch_txns = defaultdict(list)
        if os.path.exists(processor_file):
            with open(processor_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row_idx, row in enumerate(reader, start=2):
                    try:
                        gross = float(row["gross_amount"])
                        fee = float(row.get("fee_amount", 0.0))
                        net = float(row.get("net_amount", gross - fee))
                        batch_id = row.get("settlement_batch_id", "")
                        curr = row.get("currency", "USD")
                        ts = parse_iso_timestamp(row.get("timestamp", ""))

                        proc_txn = ProcessorTransaction(
                            merchant_id=row.get("merchant_id", "MERCHANT_UNKNOWN"),
                            processor_transaction_id=row["processor_transaction_id"],
                            order_id=row["order_id"],
                            processor_name="PROCESSOR",
                            event_type=row.get("event_type", "CAPTURE"),
                            gross_amount=gross,
                            fee_amount=fee,
                            net_amount=net,
                            currency=curr,
                            settlement_batch_id=batch_id,
                            timestamp=ts,
                            status=row.get("status", "SETTLED"),
                            source="BlindTest:processor_transactions",
                        )
                        dataset.processor_transactions.append(proc_txn)
                        if batch_id:
                            batch_txns[batch_id].append(proc_txn)
                    except Exception as e:
                        dataset.schema_failures.append({
                            "file": "processor_transactions.csv",
                            "row_index": row_idx,
                            "raw_row": row,
                            "error": str(e),
                        })

        # 4. Build aggregated SettlementBatch records from processor transactions
        for batch_id, txns in batch_txns.items():
            tot_gross = round(sum(t.gross_amount for t in txns), 2)
            tot_fees = round(sum(t.fee_amount for t in txns), 2)
            tot_net = round(sum(t.net_amount for t in txns), 2)
            b_curr = txns[0].currency if txns else "USD"
            b_ts = min(t.timestamp for t in txns) if txns else 0
            m_id = txns[0].merchant_id if txns else "MERCHANT_UNKNOWN"

            batch = SettlementBatch(
                merchant_id=m_id,
                batch_id=batch_id,
                processor_name="PROCESSOR",
                total_gross=tot_gross,
                total_fees=tot_fees,
                total_net=tot_net,
                currency=b_curr,
                transaction_count=len(txns),
                transaction_ids=[t.processor_transaction_id for t in txns],
                timestamp=b_ts,
                status="CLOSED",
                source="BlindTest:batch_aggregation",
            )
            dataset.batches.append(batch)

        # 5. Parse bank_transactions.csv -> BankTransactionRecord
        if os.path.exists(bank_file):
            with open(bank_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row_idx, row in enumerate(reader, start=2):
                    try:
                        amt = float(row["amount"])
                        bank_txn = BankTransactionRecord(
                            merchant_id=row.get("merchant_id", "MERCHANT_UNKNOWN"),
                            bank_transaction_id=row["bank_transaction_id"],
                            reference=row.get("reference", ""),
                            amount=amt,
                            currency=row.get("currency", "USD"),
                            timestamp=parse_iso_timestamp(row.get("timestamp", "")),
                            transaction_type=row.get("transaction_type", "CREDIT"),
                            description=row.get("description", ""),
                            source="BlindTest:bank_transactions",
                        )
                        dataset.bank_transactions.append(bank_txn)
                    except Exception as e:
                        dataset.schema_failures.append({
                            "file": "bank_transactions.csv",
                            "row_index": row_idx,
                            "raw_row": row,
                            "error": str(e),
                        })

        # 6. Parse refunds.csv -> RefundRecord
        if os.path.exists(refunds_file):
            with open(refunds_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row_idx, row in enumerate(reader, start=2):
                    try:
                        ref = RefundRecord(
                            merchant_id="MERCHANT_UNKNOWN",
                            refund_id=row["refund_id"],
                            transaction_id=row.get("transaction_id", row.get("order_id", "")),
                            order_id=row.get("order_id", ""),
                            amount=float(row["amount"]),
                            currency=row.get("currency", "USD"),
                            timestamp=parse_iso_timestamp(row.get("timestamp", "")),
                            reason=row.get("reason", "REFUND"),
                            status="PROCESSED",
                            source="BlindTest:refunds",
                        )
                        dataset.refunds.append(ref)
                    except Exception as e:
                        dataset.schema_failures.append({
                            "file": "refunds.csv",
                            "row_index": row_idx,
                            "raw_row": row,
                            "error": str(e),
                        })

        return dataset

