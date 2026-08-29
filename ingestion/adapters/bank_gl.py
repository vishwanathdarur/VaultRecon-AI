"""
Bank to General Ledger (GL) Reconciliation Adapter for VaultRecon AI.
Maps Bank Statements and GL Cash Ledger extracts into the normalized financial model.
"""

import os
import csv
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


def parse_date(date_str: str) -> int:
    """Parse YYYY-MM-DD string into integer unix timestamp."""
    if not date_str:
        return 0
    try:
        dt = datetime.strptime(date_str.strip(), "%Y-%m-%d")
        return int(dt.timestamp())
    except Exception:
        return 0


class BankGLAdapter(BaseSourceAdapter):
    def __init__(self, dataset_dir: str):
        super().__init__(source_name="BankToGL")
        self.dataset_dir = dataset_dir

    def load_dataset(self) -> NormalizedDataset:
        dataset = NormalizedDataset(source_name="BankToGL")

        # Zero fee policy for direct bank accounting / ledger reconciliations
        dataset.fee_policies.append(
            FeePolicy(
                policy_id="BANK_GL_ZERO_FEE",
                name="Bank to GL Zero Fee Policy",
                percentage_rate=0.0,
                fixed_charge=0.0,
                currency="ANY",
                payment_method="ANY",
            )
        )

        bank_file = os.path.join(self.dataset_dir, "bank_statement_jun2026.csv")
        if not os.path.exists(bank_file):
            bank_file = os.path.join(self.dataset_dir, "data", "bank_statement_jun2026.csv")

        gl_file = os.path.join(self.dataset_dir, "gl_cash_extract_jun2026.csv")
        if not os.path.exists(gl_file):
            gl_file = os.path.join(self.dataset_dir, "data", "gl_cash_extract_jun2026.csv")

        # 1. Parse GL Cash Extract -> PaymentRecord & InvoiceRecord
        if os.path.exists(gl_file):
            with open(gl_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                seen_docnos = set()
                for row_idx, row in enumerate(reader, start=2):
                    try:
                        doc_no = row.get("DocNo", "").strip()
                        raw_amt = float(row.get("Amount", "0.0"))
                        amt = abs(raw_amt)
                        date_str = row.get("Date", "").strip()
                        ts = parse_date(date_str)
                        memo = row.get("Memo", "")
                        account = row.get("Account", "")
                        is_dup = doc_no in seen_docnos
                        seen_docnos.add(doc_no)

                        tx_id = f"GL_{row_idx}_{doc_no}"
                        pay_method = "DIRECT_DEBIT" if "PAD" in memo.upper() else ("CHEQUE" if "CHQ" in doc_no.upper() else "BANK_TRANSFER")

                        pay = PaymentRecord(
                            merchant_id="CORP_OPERATING",
                            transaction_id=tx_id,
                            order_id=doc_no,
                            customer_id="CORP_OPERATING",
                            amount=amt,
                            currency="CAD",
                            payment_method=pay_method,
                            timestamp=ts,
                            status="CAPTURED",
                            source="BankGL:gl_cash_extract",
                            metadata={
                                "DocNo": doc_no,
                                "Account": account,
                                "Memo": memo,
                                "signed_amount": raw_amt,
                                "is_duplicate": is_dup,
                            },
                        )
                        dataset.payments.append(pay)

                        is_unpresented = doc_no in ("REF40947", "REF40957", "CHQ#1080", "CHQ#1082", "CHQ#1081", "CHQ#1079") or is_dup
                        dataset.ground_truth.append({
                            "work_key": tx_id,
                            "doc_no": doc_no,
                            "expected_outcome": "EXCEPTION" if is_unpresented else "MATCHED",
                        })

                        inv = InvoiceRecord(
                            merchant_id="CORP_OPERATING",
                            invoice_id=doc_no,
                            order_id=doc_no,
                            customer_id="CORP_OPERATING",
                            amount=amt,
                            currency="CAD",
                            timestamp=ts,
                            status="PAID",
                            source="BankGL:gl_cash_extract",
                            metadata={
                                "DocNo": doc_no,
                                "Account": account,
                                "Memo": memo,
                                "signed_amount": raw_amt,
                            },
                        )
                        dataset.invoices.append(inv)
                    except Exception as e:
                        dataset.schema_failures.append({
                            "file": "gl_cash_extract_jun2026.csv",
                            "row_index": row_idx,
                            "raw_row": row,
                            "error": str(e),
                        })

        # 2. Parse Bank Statement -> ProcessorTransaction & BankTransactionRecord
        if os.path.exists(bank_file):
            with open(bank_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                seen_refs = set()
                for row_idx, row in enumerate(reader, start=2):
                    try:
                        ref = row.get("Reference", "").strip()
                        raw_amt = float(row.get("Amount", "0.0"))
                        amt = abs(raw_amt)
                        date_str = row.get("Date", "").strip()
                        ts = parse_date(date_str)
                        desc = row.get("Description", "")
                        is_dup = ref in seen_refs
                        seen_refs.add(ref)

                        proc_id = f"BANK_{row_idx}_{ref}"

                        proc = ProcessorTransaction(
                            merchant_id="CORP_OPERATING",
                            processor_transaction_id=proc_id,
                            order_id=ref,
                            processor_name="BANK_STATEMENT",
                            event_type="CAPTURE" if raw_amt < 0 else "DEPOSIT",
                            gross_amount=amt,
                            fee_amount=0.0,
                            net_amount=amt,
                            currency="CAD",
                            timestamp=ts,
                            status="SETTLED",
                            source="BankGL:bank_statement",
                            metadata={
                                "Reference": ref,
                                "Description": desc,
                                "signed_amount": raw_amt,
                                "is_duplicate": is_dup,
                            },
                        )
                        dataset.processor_transactions.append(proc)

                        btx = BankTransactionRecord(
                            merchant_id="CORP_OPERATING",
                            bank_transaction_id=proc_id,
                            reference=ref,
                            amount=amt,
                            currency="CAD",
                            timestamp=ts,
                            transaction_type="DEBIT" if raw_amt < 0 else "CREDIT",
                            description=desc,
                            source="BankGL:bank_statement",
                            metadata={
                                "signed_amount": raw_amt,
                            },
                        )
                        dataset.bank_transactions.append(btx)
                    except Exception as e:
                        dataset.schema_failures.append({
                            "file": "bank_statement_jun2026.csv",
                            "row_index": row_idx,
                            "raw_row": row,
                            "error": str(e),
                        })

        return dataset

