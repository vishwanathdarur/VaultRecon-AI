"""
Invoice Payment Matcher Source Adapter for VaultRecon AI.
Maps Bank Deposits and Invoices from the invoice-payment-matcher repository into the normalized financial model.
Uses the repository's regex extractor to parse text invoices.
"""

import os
import re
import csv
import glob
from datetime import datetime
from typing import Dict, Any, List, Optional

from ingestion.adapters.base import BaseSourceAdapter, NormalizedDataset
from ingestion.schemas import (
    PaymentRecord,
    InvoiceRecord,
    ProcessorTransaction,
    BankTransactionRecord,
    FeePolicy,
)
from datasets.external.invoice_matcher.src.extractor import extract_invoice_data_regex


def parse_date(date_str: Optional[str]) -> int:
    """Parse date string into unix timestamp."""
    if not date_str:
        return 0
    date_str = date_str.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            dt = datetime.strptime(date_str, fmt)
            return int(dt.timestamp())
        except Exception:
            continue
    return 0


def clean_client_name(name: Optional[str]) -> str:
    """Normalize client name to alphanumeric uppercase token."""
    if not name:
        return "UNKNOWN_CLIENT"
    s = re.sub(r"[^A-Z0-9 ]", " ", name.upper())
    tokens = [t for t in s.split() if t not in ("WIRE", "TRANSFER", "ACH", "DEPOSIT", "CREDIT", "INC", "LLC", "CORP", "CORPORATION", "LTD", "AND", "CO") and len(t) > 1]
    return "_".join(tokens) if tokens else "CLIENT"


class InvoiceMatcherAdapter(BaseSourceAdapter):
    def __init__(self, dataset_dir: str):
        super().__init__(source_name="InvoicePaymentMatcher")
        self.dataset_dir = dataset_dir

    def load_dataset(self) -> NormalizedDataset:
        dataset = NormalizedDataset(source_name="InvoicePaymentMatcher")

        # Zero fee policy for direct invoice / bank deposit matching
        dataset.fee_policies.append(
            FeePolicy(
                policy_id="INVOICE_MATCHER_ZERO_FEE",
                name="Direct Invoice Payment Zero Fee",
                percentage_rate=0.0,
                fixed_charge=0.0,
                currency="ANY",
                payment_method="ANY",
            )
        )

        fixtures_dir = os.path.join(self.dataset_dir, "tests", "fixtures")
        bank_csv = os.path.join(fixtures_dir, "sample_bank.csv")
        if not os.path.exists(bank_csv):
            bank_csv = os.path.join(self.dataset_dir, "examples", "demo_bank_statement.csv")

        invoices_dir = os.path.join(fixtures_dir, "sample_invoices")

        # 1. Parse Invoices
        invoice_files = sorted(glob.glob(os.path.join(invoices_dir, "*.txt")))
        for row_idx, file_path in enumerate(invoice_files, start=1):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    text = f.read()

                extracted = extract_invoice_data_regex(text)
                inv_no = extracted.get("invoice_number") or f"INV_{row_idx:03d}"
                client_name = extracted.get("client_name") or "Unknown Client"
                raw_amt = extracted.get("amount") or 0.0
                date_str = extracted.get("date") or "2026-01-10"
                ts = parse_date(date_str)

                clean_client = clean_client_name(client_name)
                order_key = clean_client  # Grouping key

                inv = InvoiceRecord(
                    merchant_id="APEX_CONSULTING",
                    invoice_id=inv_no,
                    order_id=order_key,
                    customer_id=client_name,
                    amount=raw_amt,
                    currency="USD",
                    timestamp=ts,
                    status="ISSUED",
                    source="InvoiceMatcher:invoices",
                    metadata={
                        "invoice_number": inv_no,
                        "client_name": client_name,
                        "file": os.path.basename(file_path),
                        "Date": date_str,
                        "Memo": f"Invoice {inv_no} — {client_name}",
                    },
                )
                dataset.invoices.append(inv)

                # Internal receivable payment record
                pay = PaymentRecord(
                    merchant_id="APEX_CONSULTING",
                    transaction_id=f"REC_INV_{inv_no}",
                    order_id=order_key,
                    customer_id=client_name,
                    amount=raw_amt,
                    currency="USD",
                    payment_method="BANK_TRANSFER",
                    timestamp=ts,
                    status="PENDING",
                    source="InvoiceMatcher:invoices",
                    metadata={
                        "invoice_number": inv_no,
                        "client_name": client_name,
                        "Date": date_str,
                        "Memo": f"Invoice {inv_no} — {client_name}",
                    },
                )
                dataset.payments.append(pay)

                # Ground truth expectation: All 3 fixture invoices have matching bank deposits
                dataset.ground_truth.append({
                    "work_key": f"REC_INV_{inv_no}",
                    "invoice_number": inv_no,
                    "expected_outcome": "MATCHED",
                })

            except Exception as e:
                dataset.schema_failures.append({
                    "file": file_path,
                    "row_index": row_idx,
                    "error": str(e),
                })

        # 2. Parse Bank Statement Deposits
        if os.path.exists(bank_csv):
            with open(bank_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row_idx, row in enumerate(reader, start=1):
                    try:
                        date_str = row.get("Date", "").strip()
                        ts = parse_date(date_str)
                        desc = row.get("Description", "").strip()
                        raw_amt = float(row.get("Amount", "0.0").replace(",", "").replace("$", ""))
                        tx_type = row.get("Type", "Credit").strip()

                        clean_client = clean_client_name(desc)
                        order_key = clean_client
                        proc_id = f"DEP_{row_idx:03d}"

                        proc = ProcessorTransaction(
                            merchant_id="APEX_CONSULTING",
                            processor_transaction_id=proc_id,
                            order_id=order_key,
                            processor_name="BANK_DEPOSIT",
                            event_type="DEPOSIT",
                            gross_amount=raw_amt,
                            fee_amount=0.0,
                            net_amount=raw_amt,
                            currency="USD",
                            timestamp=ts,
                            status="SETTLED",
                            source="InvoiceMatcher:bank_csv",
                            metadata={
                                "Description": desc,
                                "Date": date_str,
                                "Type": tx_type,
                            },
                        )
                        dataset.processor_transactions.append(proc)

                        btx = BankTransactionRecord(
                            merchant_id="APEX_CONSULTING",
                            bank_transaction_id=proc_id,
                            reference=desc,
                            amount=raw_amt,
                            currency="USD",
                            timestamp=ts,
                            transaction_type="CREDIT",
                            description=desc,
                            source="InvoiceMatcher:bank_csv",
                            metadata={
                                "Description": desc,
                                "Date": date_str,
                            },
                        )
                        dataset.bank_transactions.append(btx)

                    except Exception as e:
                        dataset.schema_failures.append({
                            "file": bank_csv,
                            "row_index": row_idx,
                            "raw_row": row,
                            "error": str(e),
                        })

        return dataset

