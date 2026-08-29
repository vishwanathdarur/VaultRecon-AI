"""
Generalized Normalized Financial Data Schemas for VaultRecon AI.
Defines normalized, validated internal representations supporting:
- PaymentRecord
- InvoiceRecord
- ProcessorTransaction
- SettlementRecord
- SettlementBatch
- BankTransactionRecord
- RefundRecord
- AdjustmentRecord
- FeePolicy
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class FinancialRecord(BaseModel):
    record_type: str
    merchant_id: str = "DEFAULT_MERCHANT"
    currency: str = "INR"
    timestamp: int = 0
    source: str = "INTERNAL"
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_key(self) -> str:
        """Primary record storage key."""
        raise NotImplementedError

    def to_merchant_temporal_key(self) -> str:
        """Temporal secondary index key for range/prefix scans."""
        return f"IDX:MERCHANT:{self.merchant_id}:{self.timestamp:010d}:{self.record_type}:{self.to_key().split(':')[-1]}"


class PaymentRecord(FinancialRecord):
    record_type: str = "PAYMENT"
    transaction_id: str
    order_id: str
    customer_id: str = "CUST_DEFAULT"
    amount: float
    payment_method: str = "UPI"  # UPI, CREDIT_CARD, DEBIT_CARD, NET_BANKING, CARD_SYNTHETIC, WALLET_SYNTHETIC
    status: str = "SUCCESS"

    def to_key(self) -> str:
        return f"REC:PAYMENT:{self.transaction_id}"

    def to_order_key(self) -> str:
        return f"IDX:ORDER:{self.order_id}:PAYMENT:{self.transaction_id}"


class InvoiceRecord(FinancialRecord):
    record_type: str = "INVOICE"
    invoice_id: str
    order_id: str
    customer_id: str = "CUST_DEFAULT"
    amount: float
    status: str = "ISSUED"  # ISSUED, PAID, CANCELLED

    def to_key(self) -> str:
        return f"REC:INVOICE:{self.invoice_id}"

    def to_order_key(self) -> str:
        return f"IDX:ORDER:{self.order_id}:INVOICE:{self.invoice_id}"


class ProcessorTransaction(FinancialRecord):
    record_type: str = "PROCESSOR"
    processor_transaction_id: str
    order_id: str
    processor_name: str = "GATEWAY"
    event_type: str = "CAPTURE"  # CAPTURE, REFUND, CHARGEBACK, ADJUSTMENT
    gross_amount: float
    fee_amount: float = 0.0
    net_amount: float
    settlement_batch_id: Optional[str] = None
    status: str = "SETTLED"  # SETTLED, PENDING, FAILED

    def to_key(self) -> str:
        return f"REC:PROCESSOR:{self.processor_transaction_id}"

    def to_order_key(self) -> str:
        return f"IDX:ORDER:{self.order_id}:PROCESSOR:{self.processor_transaction_id}"

    def to_batch_key(self) -> Optional[str]:
        if self.settlement_batch_id:
            return f"IDX:BATCH:{self.settlement_batch_id}:PROCESSOR:{self.processor_transaction_id}"
        return None


class SettlementRecord(FinancialRecord):
    record_type: str = "SETTLEMENT"
    settlement_id: str
    transaction_id: str  # Linked transaction ID or order ID
    gross_amount: float
    fees: float
    net_amount: float
    settlement_batch_id: Optional[str] = None
    status: str = "SETTLED"  # SETTLED, HOLD, FAILED

    def to_key(self) -> str:
        return f"REC:SETTLEMENT:{self.settlement_id}"

    def to_txn_key(self) -> str:
        return f"IDX:TXN:{self.transaction_id}:SETTLEMENT:{self.settlement_id}"

    def to_batch_key(self) -> Optional[str]:
        if self.settlement_batch_id:
            return f"IDX:BATCH:{self.settlement_batch_id}:SETTLEMENT:{self.settlement_id}"
        return None


class SettlementBatch(FinancialRecord):
    record_type: str = "BATCH"
    batch_id: str
    processor_name: str = "GATEWAY"
    total_gross: float = 0.0
    total_fees: float = 0.0
    total_net: float = 0.0
    transaction_count: int = 0
    transaction_ids: List[str] = Field(default_factory=list)
    status: str = "CLOSED"  # OPEN, CLOSED, PAYOUT_INITIATED, SETTLED

    def to_key(self) -> str:
        return f"REC:BATCH:{self.batch_id}"

    def to_ref_key(self) -> str:
        clean_ref = "".join(c for c in self.batch_id.upper() if c.isalnum() or c in ("-", "_"))
        return f"IDX:REF:{clean_ref}:BATCH:{self.batch_id}"


class BankTransactionRecord(FinancialRecord):
    record_type: str = "BANK_TRANSACTION"
    bank_transaction_id: str
    reference: str  # Reference string linking to settlement batch or individual transaction
    amount: float
    transaction_type: str = "CREDIT"  # CREDIT, DEBIT
    description: str
    status: str = "POSTED"

    def to_key(self) -> str:
        return f"REC:BANK:{self.bank_transaction_id}"

    def to_ref_key(self) -> str:
        clean_ref = "".join(c for c in self.reference.upper() if c.isalnum() or c in ("-", "_"))
        return f"IDX:REF:{clean_ref}:BANK:{self.bank_transaction_id}"


class RefundRecord(FinancialRecord):
    record_type: str = "REFUND"
    refund_id: str
    transaction_id: str
    order_id: str
    amount: float
    reason: str = "CUSTOMER_REQUEST"
    status: str = "PROCESSED"

    def to_key(self) -> str:
        return f"REC:REFUND:{self.refund_id}"

    def to_order_key(self) -> str:
        return f"IDX:ORDER:{self.order_id}:REFUND:{self.refund_id}"

    def to_txn_key(self) -> str:
        return f"IDX:TXN:{self.transaction_id}:REFUND:{self.refund_id}"


class AdjustmentRecord(FinancialRecord):
    record_type: str = "ADJUSTMENT"
    adjustment_id: str
    reference_id: str
    amount: float
    adjustment_type: str = "DISPUTE_FEE"  # DISPUTE_FEE, CHARGEBACK, PENALTY, VOLUME_REBATE
    reason: str
    status: str = "APPLIED"

    def to_key(self) -> str:
        return f"REC:ADJUSTMENT:{self.adjustment_id}"


from decimal import Decimal, ROUND_HALF_UP


class FeePolicy(BaseModel):
    policy_id: str = "DEFAULT"
    name: str = "Default Policy"
    percentage_rate: float = 2.0  # Percentage e.g. 2.90 for 2.9%
    fixed_charge: float = 0.0     # Fixed flat charge e.g. 0.30
    currency: str = "ANY"
    processor: str = "ANY"
    merchant_id: str = "ANY"
    payment_method: str = "ANY"
    rounding_mode: str = "HALF_UP"

    def calculate_fee(self, gross_amount: float) -> float:
        """Calculate fee based on percentage rate + fixed charge using financial HALF_UP rounding."""
        g = Decimal(str(round(gross_amount, 4)))
        rate = Decimal(str(self.percentage_rate)) / Decimal("100")
        fix = Decimal(str(self.fixed_charge))
        raw_fee = (g * rate) + fix
        return float(raw_fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    def calculate_net(self, gross_amount: float) -> float:
        """Calculate net amount = gross - fee."""
        g = Decimal(str(round(gross_amount, 4)))
        fee = Decimal(str(self.calculate_fee(gross_amount)))
        return float((g - fee).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
