"""
Exception and Audit Trail Models for VaultRecon AI.
Defines structured financial exception objects and immutable audit logs.
"""

import time
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class AuditEvent(BaseModel):
    timestamp: float = Field(default_factory=time.time)
    action: str  # e.g., "EXCEPTION_CREATED", "AI_INVESTIGATION_STARTED", "TOOL_CALLED", "AI_DECISION", "ESCALATED_HUMAN_REVIEW"
    actor: str  # "DETERMINISTIC_MATCHER", "AI_CONTROLLER", "HUMAN_OPERATOR"
    details: Dict[str, Any] = Field(default_factory=dict)
    rationale: Optional[str] = None


class FinancialException(BaseModel):
    exception_id: str
    merchant_id: str
    exception_type: str  # AMOUNT_MISMATCH, FEE_DISCREPANCY, NOISY_BANK_REFERENCE, MISSING_SETTLEMENT, TIMING_ANOMALY, UNMATCHED_BANK_CREDIT
    primary_record_type: str
    primary_record_id: str
    related_record_ids: List[str] = Field(default_factory=list)
    expected_value: Any = None
    actual_value: Any = None
    difference: float = 0.0
    candidate_records: List[Dict[str, Any]] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    status: str = "OPEN"  # OPEN, AI_INVESTIGATING, AI_RESOLVED, HUMAN_REVIEW, RESOLVED
    resolution_reason: Optional[str] = None
    ai_confidence: Optional[float] = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    audit_trail: List[AuditEvent] = Field(default_factory=list)

    def log_event(self, action: str, actor: str, details: Optional[Dict[str, Any]] = None, rationale: Optional[str] = None):
        """Append an audit event to the exception's immutable audit log."""
        event = AuditEvent(
            timestamp=time.time(),
            action=action,
            actor=actor,
            details=details or {},
            rationale=rationale,
        )
        self.audit_trail.append(event)
        self.updated_at = time.time()

