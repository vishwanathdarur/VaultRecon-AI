"""
Evidence Object and Verified Evidence Set Models for VaultRecon AI.
Provides strict immutable evidence representations retrieved from MiniVaultDB and policy registries.
"""

import time
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class Evidence(BaseModel):
    evidence_id: str
    record_id: str
    evidence_type: str  # PAYMENT, INVOICE, PROCESSOR, BANK, SETTLEMENT, BATCH, REFUND, FEE_POLICY, CASE_PRECEDENT
    source: str = "MiniVaultDB"
    relevant_fields: Dict[str, Any] = Field(default_factory=dict)
    retrieved_at: float = Field(default_factory=time.time)
    provenance: str = "MiniVaultDB:C++_LSM"

    def to_summary_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "record_id": self.record_id,
            "type": self.evidence_type,
            "source": self.source,
            "fields": self.relevant_fields,
            "provenance": self.provenance,
        }


class EvidenceSet:
    """Manages a verified set of evidence objects collected during an investigation."""

    def __init__(self):
        self._evidence_by_id: Dict[str, Evidence] = {}
        self._evidence_by_record_id: Dict[str, List[Evidence]] = {}

    def add(self, evidence: Evidence) -> None:
        """Add an evidence item to the verified set."""
        self._evidence_by_id[evidence.evidence_id] = evidence
        self._evidence_by_record_id.setdefault(evidence.record_id, []).append(evidence)

    def get(self, evidence_id: str) -> Optional[Evidence]:
        """Retrieve evidence by its unique evidence ID."""
        return self._evidence_by_id.get(evidence_id)

    def get_by_record_id(self, record_id: str) -> List[Evidence]:
        """Retrieve all evidence associated with a given record ID."""
        return self._evidence_by_record_id.get(record_id, [])

    def contains_id(self, evidence_or_record_id: str) -> bool:
        """Check if an evidence ID or underlying record ID exists in the verified set."""
        if evidence_or_record_id in self._evidence_by_id:
            return True
        if evidence_or_record_id in self._evidence_by_record_id:
            return True
        return False

    def all_evidence_ids(self) -> List[str]:
        """List all valid evidence IDs in the verified set."""
        return list(self._evidence_by_id.keys())

    def all_record_ids(self) -> List[str]:
        """List all record IDs represented in the verified set."""
        return list(self._evidence_by_record_id.keys())

    def to_dict(self) -> Dict[str, Any]:
        """Serialize all verified evidence into a clean dictionary."""
        return {
            eid: ev.to_summary_dict() for eid, ev in self._evidence_by_id.items()
        }

    def to_prompt_context(self) -> str:
        """Format verified evidence into structured JSON lines for LLM ingestion."""
        import json
        return json.dumps(self.to_dict(), indent=2)

    def __len__(self) -> int:
        return len(self._evidence_by_id)

