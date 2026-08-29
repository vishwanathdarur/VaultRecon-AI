"""
R3n0va Synthetic Accounting Dataset Source Adapter for VaultRecon AI.
Maps accounting schema (business_invoice, payment, bank_transaction)
into the normalized financial model.
"""

import os
import csv
from datetime import datetime
from typing import Dict, Any, List, Optional

from ingestion.adapters.base import BaseSourceAdapter, NormalizedDataset
from ingestion.schemas import (
    PaymentRecord,
    InvoiceRecord,
    SettlementRecord,
    BankTransactionRecord,
    FeePolicy,
)


def parse_date(date_str: str) -> int:
    """Parse YYYY-MM-DD string into integer unix timestamp."""
    if not date_str:
        return 0
    try:
        dt = datetime.strptime(date_str.strip(), "%Y-%m-%d")
        return int(dt.timestamp())
    except Exception:
        return 0


class R3n0vaAdapter(BaseSourceAdapter):
    def __init__(self, dataset_dir: str):
        super().__init__(source_name="R3n0va")
        self.dataset_dir = dataset_dir

    def load_dataset(self) -> NormalizedDataset:
        dataset = NormalizedDataset(source_name="R3n0va")

        # Zero fee policies for corporate internal ledger accounting
        for method in ("DIRECT_DEBIT", "BANK_TRANSFER", "CARD", "SEPA_CREDIT_TRANSFER"):
            dataset.fee_policies.append(FeePolicy(
                policy_id=f"R3N0VA_{method}_ZERO",
                name=f"R3n0va Internal Ledger {method} (0%)",
                percentage_rate=0.0,
                fixed_charge=0.0,
                payment_method=method,
                currency="ANY",
            ))

        invoice_file = os.path.join(self.dataset_dir, "business_invoice.csv")
        payment_file = os.path.join(self.dataset_dir, "payment.csv")
        bank_file = os.path.join(self.dataset_dir, "bank_transaction.csv")

        # 1. Parse business_invoice.csv -> InvoiceRecord
        if os.path.exists(invoice_file):
            with open(invoice_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row_idx, row in enumerate(reader, start=2):
                    try:
                        inv = InvoiceRecord(
                            merchant_id=row.get("client_id", "MERCHANT_DEFAULT"),
                            invoice_id=row["invoice_id"],
                            order_id=row["invoice_id"],
                            customer_id=row.get("counterparty_id", "CUSTOMER_DEFAULT"),
                            amount=float(row["gross_amount"]),
                            currency=row.get("currency_code", "EUR"),
                            timestamp=parse_date(row.get("issue_date", "")),
                            status=row.get("payment_status", "OPEN"),
                            source="R3n0va:business_invoice",
                            metadata={
                                "invoice_number": row.get("invoice_number", ""),
                                "invoice_direction": row.get("invoice_direction", ""),
                                "net_amount": float(row.get("net_amount", 0.0)),
                                "vat_amount": float(row.get("vat_amount", 0.0)),
                            },
                        )
                        dataset.invoices.append(inv)
                    except Exception as e:
                        dataset.schema_failures.append({
                            "file": "business_invoice.csv",
                            "row_index": row_idx,
                            "raw_row": row,
                            "error": str(e),
                        })

        # 2. Parse payment.csv -> PaymentRecord & SettlementRecord
        if os.path.exists(payment_file):
            with open(payment_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row_idx, row in enumerate(reader, start=2):
                    try:
                        amt = float(row["payment_amount"])
                        ts = parse_date(row.get("payment_date", ""))
                        curr = row.get("currency_code", "EUR")
                        pay_id = row["payment_id"]
                        inv_id = row["invoice_id"]
                        client_id = row.get("client_id", "MERCHANT_DEFAULT")
                        method = row.get("payment_method", "BANK_TRANSFER")

                        pay = PaymentRecord(
                            merchant_id=client_id,
                            transaction_id=pay_id,
                            order_id=inv_id,
                            customer_id=client_id,
                            amount=amt,
                            currency=curr,
                            payment_method=method,
                            timestamp=ts,
                            status="CAPTURED",
                            source="R3n0va:payment",
                            metadata={"is_partial": row.get("is_partial", "False")},
                        )
                        dataset.payments.append(pay)

                        settle = SettlementRecord(
                            merchant_id=client_id,
                            settlement_id=pay_id,
                            transaction_id=pay_id,
                            order_id=inv_id,
                            gross_amount=amt,
                            fees=0.0,
                            net_amount=amt,
                            currency=curr,
                            status="SETTLED",
                            source="R3n0va:payment_settlement",
                        )
                        dataset.settlements.append(settle)
                    except Exception as e:
                        dataset.schema_failures.append({
                            "file": "payment.csv",
                            "row_index": row_idx,
                            "raw_row": row,
                            "error": str(e),
                        })

        # 3. Parse bank_transaction.csv -> BankTransactionRecord
        if os.path.exists(bank_file):
            with open(bank_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row_idx, row in enumerate(reader, start=2):
                    try:
                        amt = float(row["transaction_amount"])
                        ts = parse_date(row.get("transaction_date", ""))
                        curr = row.get("currency_code", "EUR")
                        btx_id = row["bank_transaction_id"]
                        client_id = row.get("client_id", "MERCHANT_DEFAULT")
                        ref = row.get("reference_text", "")
                        ttype = row.get("transaction_type", "CUSTOMER_PAYMENT")

                        bank_txn = BankTransactionRecord(
                            merchant_id=client_id,
                            bank_transaction_id=btx_id,
                            reference=ref,
                            amount=amt,
                            currency=curr,
                            timestamp=ts,
                            transaction_type="CREDIT" if "PAYMENT" in ttype else "DEBIT",
                            description=f"{ttype} - {ref}",
                            source="R3n0va:bank_transaction",
                        )
                        dataset.bank_transactions.append(bank_txn)
                    except Exception as e:
                        dataset.schema_failures.append({
                            "file": "bank_transaction.csv",
                            "row_index": row_idx,
                            "raw_row": row,
                            "error": str(e),
                        })

        return dataset
