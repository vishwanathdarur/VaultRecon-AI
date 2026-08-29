"""
Source Adapter Layer for VaultRecon AI.
Converts heterogeneous external financial sources into normalized records.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pydantic import BaseModel

from ingestion.schemas import (
    PaymentRecord,
    InvoiceRecord,
    ProcessorTransaction,
    SettlementRecord,
    SettlementBatch,
    BankTransactionRecord,
    RefundRecord,
    AdjustmentRecord,
    FeePolicy,
)


@dataclass
class NormalizedDataset:
    source_name: str
    payments: List[PaymentRecord] = field(default_factory=list)
    invoices: List[InvoiceRecord] = field(default_factory=list)
    processor_transactions: List[ProcessorTransaction] = field(default_factory=list)
    settlements: List[SettlementRecord] = field(default_factory=list)
    batches: List[SettlementBatch] = field(default_factory=list)
    bank_transactions: List[BankTransactionRecord] = field(default_factory=list)
    refunds: List[RefundRecord] = field(default_factory=list)
    adjustments: List[AdjustmentRecord] = field(default_factory=list)
    fee_policies: List[FeePolicy] = field(default_factory=list)
    ground_truth: List[Dict[str, Any]] = field(default_factory=list)
    schema_failures: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def total_records(self) -> int:
        return (
            len(self.payments)
            + len(self.invoices)
            + len(self.processor_transactions)
            + len(self.settlements)
            + len(self.batches)
            + len(self.bank_transactions)
            + len(self.refunds)
            + len(self.adjustments)
        )


class BaseSourceAdapter:
    """Abstract base class for all source adapters."""

    def __init__(self, source_name: str):
        self.source_name = source_name

    def load_dataset(self) -> NormalizedDataset:
        """Load and normalize source data into NormalizedDataset."""
        raise NotImplementedError

