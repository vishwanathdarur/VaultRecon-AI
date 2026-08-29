"""
Generic CSV Source Adapter for VaultRecon AI.
Allows loading arbitrary external CSV files by defining custom column mappings.
"""

import os
import csv
from typing import Dict, Any, Optional
from ingestion.adapters.base import BaseSourceAdapter, NormalizedDataset
from ingestion.schemas import PaymentRecord, InvoiceRecord, ProcessorTransaction, BankTransactionRecord


class GenericCSVAdapter(BaseSourceAdapter):
    def __init__(
        self,
        file_path: str,
        record_type: str,
        column_mapping: Dict[str, str],
        source_name: str = "GenericCSV",
    ):
        super().__init__(source_name=source_name)
        self.file_path = file_path
        self.record_type = record_type.upper()
        self.column_mapping = column_mapping

    def load_dataset(self) -> NormalizedDataset:
        dataset = NormalizedDataset(source_name=self.source_name)

        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"CSV file not found: {self.file_path}")

        with open(self.file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row_idx, row in enumerate(reader, start=2):
                try:
                    mapped = {target_k: row.get(src_k) for target_k, src_k in self.column_mapping.items()}
                    if self.record_type == "PAYMENT":
                        pay = PaymentRecord(
                            merchant_id=mapped.get("merchant_id", "DEFAULT"),
                            transaction_id=str(mapped["transaction_id"]),
                            order_id=str(mapped["order_id"]),
                            amount=float(mapped["amount"]),
                            currency=mapped.get("currency", "USD"),
                            timestamp=int(float(mapped.get("timestamp", 0))),
                            source=self.source_name,
                        )
                        dataset.payments.append(pay)
                    elif self.record_type == "PROCESSOR":
                        proc = ProcessorTransaction(
                            merchant_id=mapped.get("merchant_id", "DEFAULT"),
                            processor_transaction_id=str(mapped["processor_transaction_id"]),
                            order_id=str(mapped["order_id"]),
                            gross_amount=float(mapped["gross_amount"]),
                            fee_amount=float(mapped.get("fee_amount", 0.0)),
                            net_amount=float(mapped["net_amount"]),
                            currency=mapped.get("currency", "USD"),
                            timestamp=int(float(mapped.get("timestamp", 0))),
                            source=self.source_name,
                        )
                        dataset.processor_transactions.append(proc)
                except Exception as e:
                    dataset.schema_failures.append({
                        "file": self.file_path,
                        "row_index": row_idx,
                        "raw_row": row,
                        "error": str(e),
                    })

        return dataset

