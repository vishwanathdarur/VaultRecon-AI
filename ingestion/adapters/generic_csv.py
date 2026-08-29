"""
Generic CSV Source Adapter for VaultRecon AI.
Allows loading arbitrary external CSV files by defining custom column mappings.
Supports single-file or multi-file mapping across payments, invoices, processors, bank records, refunds, and fee policies.
"""

import os
import csv
from typing import Dict, Any, Optional, Union, List
from ingestion.adapters.base import BaseSourceAdapter, NormalizedDataset
from ingestion.schemas import (
    PaymentRecord,
    InvoiceRecord,
    ProcessorTransaction,
    BankTransactionRecord,
    RefundRecord,
    SettlementBatch,
    FeePolicy,
)


class GenericCSVAdapter(BaseSourceAdapter):
    def __init__(
        self,
        file_path: Optional[str] = None,
        record_type: Optional[str] = None,
        column_mapping: Optional[Dict[str, str]] = None,
        file_paths: Optional[Dict[str, str]] = None,
        column_mappings: Optional[Dict[str, Dict[str, str]]] = None,
        source_name: str = "GenericCSV",
    ):
        super().__init__(source_name=source_name)
        self.file_path = file_path
        self.record_type = record_type.upper() if record_type else None
        self.column_mapping = column_mapping or {}
        self.file_paths = file_paths or {}
        self.column_mappings = column_mappings or {}

    def _ingest_file(self, file_path: str, record_type: str, mapping: Dict[str, str], dataset: NormalizedDataset):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"CSV file not found: {file_path}")

        rtype = record_type.upper().rstrip("S")  # Normalize e.g. PAYMENTS -> PAYMENT

        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row_idx, row in enumerate(reader, start=2):
                try:
                    mapped = {target_k: row.get(src_k) for target_k, src_k in mapping.items()}
                    
                    if rtype in ("PAYMENT", "ORDER"):
                        pay = PaymentRecord(
                            merchant_id=mapped.get("merchant_id") or "DEFAULT",
                            transaction_id=str(mapped["transaction_id"]),
                            order_id=str(mapped["order_id"]),
                            customer_id=mapped.get("customer_id") or "UNKNOWN_CUST",
                            amount=float(mapped["amount"]),
                            currency=mapped.get("currency") or "USD",
                            payment_method=mapped.get("payment_method") or "CREDIT_CARD",
                            timestamp=int(float(mapped.get("timestamp") or 0)),
                            source=self.source_name,
                        )
                        dataset.payments.append(pay)

                    elif rtype in ("PROCESSOR", "PROCESSOR_TRANSACTION", "GATEWAY"):
                        gross = float(mapped["gross_amount"])
                        fee = float(mapped.get("fee_amount") or 0.0)
                        net = float(mapped.get("net_amount") or (gross - fee))
                        proc = ProcessorTransaction(
                            merchant_id=mapped.get("merchant_id") or "DEFAULT",
                            processor_transaction_id=str(mapped["processor_transaction_id"]),
                            order_id=str(mapped["order_id"]),
                            processor=mapped.get("processor") or "GATEWAY",
                            gross_amount=gross,
                            fee_amount=fee,
                            net_amount=net,
                            currency=mapped.get("currency") or "USD",
                            timestamp=int(float(mapped.get("timestamp") or 0)),
                            source=self.source_name,
                        )
                        dataset.processor_transactions.append(proc)

                    elif rtype in ("INVOICE", "BILL"):
                        inv = InvoiceRecord(
                            merchant_id=mapped.get("merchant_id") or "DEFAULT",
                            invoice_id=str(mapped["invoice_id"]),
                            order_id=str(mapped["order_id"]),
                            customer_id=mapped.get("customer_id") or "UNKNOWN_CUST",
                            amount=float(mapped["amount"]),
                            currency=mapped.get("currency") or "USD",
                            timestamp=int(float(mapped.get("timestamp") or 0)),
                            source=self.source_name,
                        )
                        dataset.invoices.append(inv)

                    elif rtype in ("BANK", "BANK_TRANSACTION", "BANK_TXN", "DEPOSIT"):
                        bank = BankTransactionRecord(
                            merchant_id=mapped.get("merchant_id") or "DEFAULT",
                            bank_transaction_id=str(mapped["bank_transaction_id"]),
                            reference=str(mapped.get("reference") or mapped.get("order_id") or mapped["bank_transaction_id"]),
                            amount=float(mapped["amount"]),
                            currency=mapped.get("currency") or "USD",
                            description=mapped.get("description") or "Bank Entry",
                            timestamp=int(float(mapped.get("timestamp") or 0)),
                            source=self.source_name,
                        )
                        dataset.bank_transactions.append(bank)

                    elif rtype in ("REFUND", "CHARGEBACK"):
                        ref = RefundRecord(
                            merchant_id=mapped.get("merchant_id") or "DEFAULT",
                            refund_id=str(mapped["refund_id"]),
                            transaction_id=str(mapped.get("transaction_id") or mapped.get("order_id") or mapped["refund_id"]),
                            order_id=str(mapped["order_id"]),
                            amount=float(mapped["amount"]),
                            currency=mapped.get("currency") or "USD",
                            timestamp=int(float(mapped.get("timestamp") or 0)),
                            source=self.source_name,
                        )
                        dataset.refunds.append(ref)

                except Exception as e:
                    dataset.schema_failures.append({
                        "file": file_path,
                        "row_index": row_idx,
                        "raw_row": row,
                        "error": str(e),
                    })

    def load_dataset(self) -> NormalizedDataset:
        dataset = NormalizedDataset(source_name=self.source_name)

        # Mode A: Multi-file dict
        if self.file_paths:
            for rtype, fpath in self.file_paths.items():
                mapping = self.column_mappings.get(rtype, {})
                self._ingest_file(fpath, rtype, mapping, dataset)

        # Mode B: Single-file args
        elif self.file_path and self.record_type:
            self._ingest_file(self.file_path, self.record_type, self.column_mapping, dataset)

        return dataset

