"""
Autonomous AI Exception Controller for VaultRecon AI.
Investigates financial exceptions using controlled read-only tools, builds verified evidence sets,
evaluates policies, and applies strict anti-hallucination and fact-checking guardrails.
"""

import re
import json
import time
from typing import Dict, Any, Optional, List, Tuple
from pydantic import BaseModel, Field

from recon.storage import MiniVaultDBClient
from recon.exceptions import FinancialException, AuditEvent
from recon.rules import GLOBAL_FEE_REGISTRY, FeePolicyRegistry
from ai.tools import InvestigationToolkit
from ai.evidence import Evidence, EvidenceSet
from ai.guardrails import DecisionPolicy, ValidationResult
from ai.prompts import SYSTEM_PROMPT, INVESTIGATION_PROMPT_TEMPLATE
from ai.llm import BaseLLMProvider, get_llm_provider


class AIDecisionResult(BaseModel):
    decision: str  # AI_RESOLVED or HUMAN_REVIEW
    exception_type: str
    confidence: float
    reason: str
    evidence_ids: List[str] = Field(default_factory=list)
    recommended_action: str
    findings: List[str] = Field(default_factory=list)
    raw_response: Optional[str] = None
    verification_passed: bool = True
    validation_reason: Optional[str] = None
    investigation_duration_ms: float = 0.0


class AIController:
    def __init__(
        self,
        db_client: MiniVaultDBClient,
        llm_provider: Optional[BaseLLMProvider] = None,
        fee_registry: Optional[FeePolicyRegistry] = None,
        confidence_threshold: float = 0.85,
    ):
        self.db = db_client
        self.fee_registry = fee_registry or GLOBAL_FEE_REGISTRY
        self.toolkit = InvestigationToolkit(db_client, self.fee_registry)
        self.llm = llm_provider or get_llm_provider()
        self.decision_policy = DecisionPolicy(confidence_threshold=confidence_threshold)

    def investigate(self, exception: FinancialException) -> AIDecisionResult:
        """
        Full AI investigation workflow:
        1. Tool Execution -> Build EvidenceSet from MiniVaultDB
        2. Format Prompt with Isolated Untrusted Data
        3. Query LLM Provider
        4. Guardrails & Fact Validation
        5. Append-Only Audit Logging & Exception State Transition
        """
        t_start = time.perf_counter()

        exception.log_event("AI_INVESTIGATION_STARTED", "AI_CONTROLLER", {
            "exception_id": exception.exception_id,
            "exception_type": exception.exception_type,
            "primary_record_id": exception.primary_record_id,
        })

        # Step 1: Tool Execution & EvidenceSet Construction
        evidence_set = EvidenceSet()
        tools_called: List[str] = []

        # 1a. Primary Record Lookup
        prim_ev = self.toolkit.get_record(exception.primary_record_type, exception.primary_record_id)
        if prim_ev:
            evidence_set.add(prim_ev)
            tools_called.append(f"get_record({exception.primary_record_type}, {exception.primary_record_id})")

        # 1b. Related Record Lookups
        for rel_id in exception.related_record_ids:
            # Check by order
            order_records = self.toolkit.search_by_order(rel_id)
            for ev in order_records:
                evidence_set.add(ev)
                tools_called.append(f"search_by_order({rel_id})")

            # Check individual record types if not found by order
            if not order_records:
                for rtype in ["PAYMENT", "PROCESSOR", "INVOICE", "BANK", "SETTLEMENT", "BATCH", "REFUND"]:
                    ev = self.toolkit.get_record(rtype, rel_id)
                    if ev:
                        evidence_set.add(ev)
                        tools_called.append(f"get_record({rtype}, {rel_id})")

        # 1c. Fee Policy Lookup (for Fee Discrepancies)
        if exception.exception_type in ("FEE_MISMATCH", "FEE_DISCREPANCY", "UNKNOWN_FEE_POLICY"):
            pay_evs = [ev for ev in evidence_set._evidence_by_id.values() if ev.evidence_type == "PAYMENT"]
            proc_evs = [ev for ev in evidence_set._evidence_by_id.values() if ev.evidence_type == "PROCESSOR"]
            pay_method = pay_evs[0].relevant_fields.get("payment_method") if pay_evs else None
            currency = pay_evs[0].relevant_fields.get("currency") if pay_evs else (proc_evs[0].relevant_fields.get("currency") if proc_evs else None)
            proc_name = proc_evs[0].relevant_fields.get("processor_name") if proc_evs else None

            if pay_method or proc_name or currency:
                pol_ev = self.toolkit.get_fee_policy(
                    merchant_id=exception.merchant_id,
                    processor=proc_name,
                    payment_method=pay_method,
                    currency=currency,
                )
                if pol_ev:
                    evidence_set.add(pol_ev)
                    tools_called.append(f"get_fee_policy({exception.merchant_id}, {pay_method})")

        # 1d. Bundled Payment / Customer Invoices Lookup
        if "BUNDLED" in exception.exception_type or len(evidence_set.get_by_record_id(exception.primary_record_id)) > 1:
            all_cust_keys = [exception.primary_record_id] + list(exception.related_record_ids)
            for ckey in all_cust_keys:
                cust_records = self.toolkit.search_by_customer(ckey)
                for ev in cust_records:
                    evidence_set.add(ev)
                    tools_called.append(f"search_by_customer({ckey})")

        # 1e. Case Precedents
        precedents = self.toolkit.get_similar_cases(exception.exception_type)
        for ev in precedents:
            evidence_set.add(ev)

        # Step 2: Format Isolated Prompt Context
        raw_meta = str(exception.metadata.get("findings", "")) + " " + str(exception.candidate_records)
        user_prompt = INVESTIGATION_PROMPT_TEMPLATE.format(
            exception_id=exception.exception_id,
            exception_type=exception.exception_type,
            merchant_id=exception.merchant_id,
            primary_record_type=exception.primary_record_type,
            primary_record_id=exception.primary_record_id,
            related_record_ids=", ".join(str(r) for r in exception.related_record_ids),
            expected_value=exception.expected_value,
            actual_value=exception.actual_value,
            difference=exception.difference,
            reason=exception.audit_trail[0].details.get("reason", "") if exception.audit_trail else "",
            raw_metadata=raw_meta,
            tool_evidence=evidence_set.to_prompt_context(),
            case_precedents=json.dumps([p.relevant_fields for p in precedents], indent=2),
        )

        # Step 3: Query LLM Provider
        try:
            raw_response = self.llm.generate(SYSTEM_PROMPT, user_prompt)
        except Exception as e:
            t_end = time.perf_counter()
            decision_result = AIDecisionResult(
                decision="HUMAN_REVIEW",
                exception_type=exception.exception_type,
                confidence=0.50,
                reason=f"LLM investigation execution failed: {str(e)}. Safely escalated to human controller.",
                evidence_ids=[],
                recommended_action="escalate_to_finance_controller",
                findings=["LLM provider invocation failure."],
                raw_response=None,
                verification_passed=False,
                validation_reason="LLM_EXECUTION_ERROR",
                investigation_duration_ms=(t_end - t_start) * 1000.0,
            )
            exception.status = "HUMAN_REVIEW"
            exception.resolution_reason = decision_result.reason
            exception.ai_confidence = decision_result.confidence
            exception.log_event("AI_DECISION", "AI_CONTROLLER", decision_result.model_dump(), rationale=decision_result.reason)
            return decision_result

        # Step 4: Parse Structured JSON
        parsed_data = self._parse_json_response(raw_response)
        if not parsed_data:
            t_end = time.perf_counter()
            decision_result = AIDecisionResult(
                decision="HUMAN_REVIEW",
                exception_type=exception.exception_type,
                confidence=0.50,
                reason="AI returned malformed or non-JSON output format. Escalated for safety.",
                evidence_ids=[],
                recommended_action="escalate_to_finance_controller",
                findings=["Malformed JSON response."],
                raw_response=raw_response,
                verification_passed=False,
                validation_reason="MALFORMED_JSON_RESPONSE",
                investigation_duration_ms=(t_end - t_start) * 1000.0,
            )
            exception.status = "HUMAN_REVIEW"
            exception.resolution_reason = decision_result.reason
            exception.ai_confidence = decision_result.confidence
            exception.log_event("AI_DECISION", "AI_CONTROLLER", decision_result.model_dump(), rationale=decision_result.reason)
            return decision_result

        raw_dec = parsed_data.get("decision", "HUMAN_REVIEW").upper()
        confidence = float(parsed_data.get("confidence", 0.70))
        reason = parsed_data.get("reason", "No detailed rationale provided.")
        evidence_ids = parsed_data.get("evidence_ids", parsed_data.get("evidence", []))
        rec_action = parsed_data.get("recommended_action", "escalate_to_finance_controller")
        findings = parsed_data.get("findings", [])

        # Step 5: Guardrails & Fact Validation
        val_res: ValidationResult = self.decision_policy.evaluate_decision(
            raw_decision=raw_dec,
            confidence=confidence,
            reason=reason,
            cited_evidence_ids=evidence_ids,
            evidence_set=evidence_set,
            exception=exception,
        )

        final_decision = "AI_RESOLVED" if (raw_dec in ("RESOLVED", "AI_RESOLVED") and val_res.passed) else "HUMAN_REVIEW"
        if not val_res.passed:
            reason = f"Guardrail Escalation: {val_res.reason} (Original LLM Proposal: {reason})"
            confidence = min(confidence, 0.75)

        t_end = time.perf_counter()
        duration_ms = (t_end - t_start) * 1000.0
        final_exc_type = parsed_data.get("exception_type", exception.exception_type)

        decision_result = AIDecisionResult(
            decision=final_decision,
            exception_type=final_exc_type,
            confidence=confidence,
            reason=reason,
            evidence_ids=val_res.verified_ids,
            recommended_action=rec_action,
            findings=findings,
            raw_response=raw_response,
            verification_passed=val_res.passed,
            validation_reason=val_res.reason,
            investigation_duration_ms=duration_ms,
        )

        # Step 6: Update Exception Status & Log Immutable Audit Trail
        exception.status = final_decision
        exception.resolution_reason = reason
        exception.ai_confidence = confidence
        exception.evidence = val_res.verified_ids

        exception.log_event("AI_INVESTIGATION_COMPLETED", "AI_CONTROLLER", {
            "decision": final_decision,
            "confidence": confidence,
            "verified_evidence_ids": val_res.verified_ids,
            "unverified_evidence_ids": val_res.unverified_ids,
            "tools_called": tools_called,
            "duration_ms": duration_ms,
            "guardrail_passed": val_res.passed,
        }, rationale=reason)

        return decision_result

    def _parse_json_response(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse structured JSON from raw LLM string."""
        if not text or not isinstance(text, str):
            return None
        text = text.strip()
        try:
            return json.loads(text)
        except Exception:
            pass

        # Try markdown code block extraction
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass

        # Try outer brace regex extraction
        match2 = re.search(r"(\{.*\})", text, re.DOTALL)
        if match2:
            try:
                return json.loads(match2.group(1))
            except Exception:
                pass

        return None
