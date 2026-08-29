"""
Controlled Read-Only Investigation Tools for AI Controller.
Provides strict, read-only access to MiniVaultDB, fee schedules, and historical case knowledge,
returning structured, immutable Evidence objects with full provenance.
"""

from typing import Dict, Any, List, Optional
from recon.storage import MiniVaultDBClient
from recon.rules import GLOBAL_FEE_REGISTRY, FeePolicyRegistry
from ai.evidence import Evidence, EvidenceSet


HISTORICAL_CASES = [
    {
        "case_id": "HIST_001",
        "exception_type": "FEE_DISCREPANCY",
        "condition": "International card surcharge of 3.5%",
        "resolution": "RESOLVED",
        "rule_id": "RULE_INTL_CARD_3.5",
        "rationale": "Merchant agreed to 3.5% rate for cross-border card transactions.",
    },
    {
        "case_id": "HIST_002",
        "exception_type": "NOISY_BANK_REFERENCE",
        "condition": "Bank narrative contains order ID or settlement suffix within 48 hours",
        "resolution": "RESOLVED",
        "rationale": "Bank narrative truncates prefix but preserves trailing unique identifier.",
    },
    {
        "case_id": "HIST_003",
        "exception_type": "AMOUNT_MISMATCH",
        "condition": "Invoice amount higher than payment with no coupon/credit applied",
        "resolution": "HUMAN_REVIEW",
        "rationale": "Unexplained underpayment must be routed to collections or billing support.",
    },
]


class InvestigationToolkit:
    """Strict read-only tool layer providing immutable Evidence objects for AI Controller."""

    def __init__(self, db_client: MiniVaultDBClient, fee_registry: Optional[FeePolicyRegistry] = None):
        self.db = db_client
        self.fee_registry = fee_registry or GLOBAL_FEE_REGISTRY

    def get_record(self, record_type: str, record_id: str) -> Optional[Evidence]:
        """Generic read-only record lookup by type and ID."""
        rec_type = record_type.upper()
        data = self.db.get_record(rec_type, record_id)
        if not data:
            return None
        return Evidence(
            evidence_id=f"EVID_{rec_type}_{record_id}",
            record_id=record_id,
            evidence_type=rec_type,
            source="MiniVaultDB",
            relevant_fields=data,
            provenance=f"MiniVaultDB:REC:{rec_type}:{record_id}",
        )

    def get_payment(self, payment_id: str) -> Optional[Evidence]:
        """Retrieve payment transaction details from MiniVaultDB."""
        return self.get_record("PAYMENT", payment_id)

    def get_processor_transaction(self, processor_transaction_id: str) -> Optional[Evidence]:
        """Retrieve processor transaction details from MiniVaultDB."""
        return self.get_record("PROCESSOR", processor_transaction_id)

    def get_settlement(self, settlement_id: str) -> Optional[Evidence]:
        """Retrieve gateway settlement details from MiniVaultDB."""
        return self.get_record("SETTLEMENT", settlement_id)

    def get_settlement_batch(self, batch_id: str) -> Optional[Evidence]:
        """Retrieve settlement batch details from MiniVaultDB."""
        return self.get_record("BATCH", batch_id)

    def get_invoice(self, invoice_id: str) -> Optional[Evidence]:
        """Retrieve invoice details from MiniVaultDB."""
        return self.get_record("INVOICE", invoice_id)

    def get_bank_transaction(self, bank_transaction_id: str) -> Optional[Evidence]:
        """Retrieve bank deposit details from MiniVaultDB."""
        return self.get_record("BANK", bank_transaction_id)

    def get_refund(self, refund_id: str) -> Optional[Evidence]:
        """Retrieve refund record details from MiniVaultDB."""
        return self.get_record("REFUND", refund_id)

    def search_by_order(self, order_id: str) -> List[Evidence]:
        """Retrieve all records indexed under an order ID."""
        results: List[Evidence] = []
        for rec_type in ["PAYMENT", "INVOICE", "PROCESSOR", "REFUND", "ADJUSTMENT"]:
            indexes = self.db.scan_prefix(f"IDX:ORDER:{order_id}:{rec_type}:")
            for _, pk in indexes:
                rec_id = pk.split(":")[-1]
                ev = self.get_record(rec_type, rec_id)
                if ev:
                    results.append(ev)
        return results

    def search_by_reference(self, reference: str) -> List[Evidence]:
        """Search bank deposits and settlements by reference substring."""
        clean_ref = "".join(c for c in reference.upper() if c.isalnum() or c in ("-", "_"))
        results: List[Evidence] = []
        indexes = self.db.scan_prefix(f"IDX:REF:{clean_ref}:")
        for _, pk in indexes:
            parts = pk.split(":")
            if len(parts) >= 3:
                rec_type = parts[1]
                rec_id = parts[2]
                ev = self.get_record(rec_type, rec_id)
                if ev:
                    results.append(ev)
        return results

    def search_by_customer(self, customer_id: str) -> List[Evidence]:
        """Retrieve all invoices and payments associated with a customer ID using secondary indexes."""
        return self.search_by_order(customer_id)

    def get_fee_policy(
        self,
        merchant_id: Optional[str] = None,
        processor: Optional[str] = None,
        payment_method: Optional[str] = None,
        currency: Optional[str] = None,
    ) -> Optional[Evidence]:
        """Fetch matching contractual fee policy."""
        policy = self.fee_registry.match_policy(
            merchant_id=merchant_id,
            processor=processor,
            payment_method=payment_method,
            currency=currency,
        )
        if not policy:
            return None
        return Evidence(
            evidence_id=f"EVID_POLICY_{policy.policy_id}",
            record_id=policy.policy_id,
            evidence_type="FEE_POLICY",
            source="FeePolicyRegistry",
            relevant_fields={
                "policy_id": policy.policy_id,
                "name": policy.name,
                "percentage_rate": policy.percentage_rate,
                "fixed_charge": policy.fixed_charge,
                "currency": policy.currency,
                "payment_method": policy.payment_method,
                "processor": policy.processor,
            },
            provenance=f"FeePolicyRegistry:{policy.policy_id}",
        )

    def get_similar_cases(self, exception_type: str) -> List[Evidence]:
        """Retrieve historical resolution precedents for similar exception types."""
        results: List[Evidence] = []
        for c in HISTORICAL_CASES:
            if c["exception_type"] == exception_type:
                results.append(Evidence(
                    evidence_id=f"EVID_PRECEDENT_{c['case_id']}",
                    record_id=c["case_id"],
                    evidence_type="CASE_PRECEDENT",
                    source="PrecedentLibrary",
                    relevant_fields=c,
                    provenance=f"PrecedentLibrary:{c['case_id']}",
                ))
        return results
