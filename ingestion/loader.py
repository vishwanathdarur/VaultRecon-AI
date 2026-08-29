"""
High-Throughput Ingestion Loader for MiniVaultDB.
Loads normalized datasets into MiniVaultDB and tracks ingestion metrics.
"""

import time
from typing import TYPE_CHECKING, Dict, Any, Optional
from dataclasses import dataclass

if TYPE_CHECKING:
    from recon.storage import MiniVaultDBClient


@dataclass
class IngestionReport:
    total_records: int
    payments_count: int
    invoices_count: int
    processor_txns_count: int
    settlements_count: int
    batches_count: int
    bank_txns_count: int
    refunds_count: int
    adjustments_count: int
    duration_sec: float
    throughput_records_per_sec: float


class IngestionLoader:
    def __init__(self, db_client: Any):
        self.db = db_client

    def load_dataset(self, dataset: Any) -> IngestionReport:
        t_start = time.perf_counter()

        invoices = getattr(dataset, "invoices", [])
        payments = getattr(dataset, "payments", [])
        processor_txns = getattr(dataset, "processor_transactions", [])
        settlements = getattr(dataset, "settlements", [])
        batches = getattr(dataset, "batches", [])
        bank_txns = getattr(dataset, "bank_transactions", [])
        refunds = getattr(dataset, "refunds", [])
        adjustments = getattr(dataset, "adjustments", [])

        for inv in invoices:
            self.db.put_record(inv)
        for pay in payments:
            self.db.put_record(pay)
        for proc in processor_txns:
            self.db.put_record(proc)
        for settle in settlements:
            self.db.put_record(settle)
        for batch in batches:
            self.db.put_record(batch)
        for bank in bank_txns:
            self.db.put_record(bank)
        for ref in refunds:
            self.db.put_record(ref)
        for adj in adjustments:
            self.db.put_record(adj)

        t_end = time.perf_counter()
        dur = max(t_end - t_start, 1e-6)
        tot = (
            len(invoices)
            + len(payments)
            + len(processor_txns)
            + len(settlements)
            + len(batches)
            + len(bank_txns)
            + len(refunds)
            + len(adjustments)
        )

        return IngestionReport(
            total_records=tot,
            payments_count=len(payments),
            invoices_count=len(invoices),
            processor_txns_count=len(processor_txns),
            settlements_count=len(settlements),
            batches_count=len(batches),
            bank_txns_count=len(bank_txns),
            refunds_count=len(refunds),
            adjustments_count=len(adjustments),
            duration_sec=dur,
            throughput_records_per_sec=round(tot / dur, 2),
        )
