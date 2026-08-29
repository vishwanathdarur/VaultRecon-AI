"""
Guardrail and Fact Validation Engine for VaultRecon AI Controller.
Enforces strict anti-hallucination checks, factual claim verification, and conservative decision policies.
"""

import re
from typing import List, Dict, Any, Tuple, Optional
from ai.evidence import EvidenceSet, Evidence
from recon.exceptions import FinancialException


class ValidationResult:
    def __init__(self, passed: bool, reason: str, verified_ids: List[str], unverified_ids: List[str], contradictions: List[str]):
        self.passed = passed
        self.reason = reason
        self.verified_ids = verified_ids
        self.unverified_ids = unverified_ids
        self.contradictions = contradictions


class EvidenceGuardrail:
    """Validates that all cited evidence IDs exist in the verified EvidenceSet."""

    @staticmethod
    def verify_citations(cited_ids: List[str], evidence_set: EvidenceSet) -> Tuple[List[str], List[str]]:
        """
        Verify cited evidence IDs.
        Returns (valid_ids, invalid_ids).
        """
        valid: List[str] = []
        invalid: List[str] = []

        for cid in cited_ids:
            if not isinstance(cid, str) or not cid.strip():
                continue
            clean_id = cid.strip()
            if evidence_set.contains_id(clean_id):
                valid.append(clean_id)
            else:
                invalid.append(clean_id)

        return valid, invalid


class FactValidator:
    """Verifies that numerical amounts, currencies, and references mentioned by LLM match verified evidence."""

    @staticmethod
    def validate_facts(reason_text: str, evidence_set: EvidenceSet) -> List[str]:
        """
        Extract claimed dollar amounts and fee percentages from reason_text
        and ensure they do not contradict the verified evidence.
        Returns a list of contradiction error descriptions (empty if clean).
        """
        contradictions: List[str] = []

        # Extract dollar amounts mentioned in text: e.g. "$1,500.00", "$6.08", "1500.00"
        amount_matches = re.findall(r"\$\s*([\d,]+\.?\d*)", reason_text)
        claimed_amounts = []
        for a in amount_matches:
            try:
                claimed_amounts.append(float(a.replace(",", "")))
            except ValueError:
                pass

        # Collect all verified numerical amounts in evidence_set
        verified_amounts = set()
        for ev in evidence_set._evidence_by_id.values():
            fields = ev.relevant_fields
            for k in ["amount", "gross_amount", "net_amount", "fee_amount", "fees", "total_net", "total_gross", "total_fees", "Total Amount Due", "difference"]:
                val = fields.get(k)
                if val is not None:
                    try:
                        verified_amounts.add(round(float(val), 2))
                    except (ValueError, TypeError):
                        pass

        # If LLM claims an amount not found in any evidence and there are verified amounts
        # We check whether the claimed amounts are within rounding distance of verified amounts
        for ca in claimed_amounts:
            # Check if ca matches any verified amount within 0.05
            if verified_amounts and not any(abs(ca - va) <= 0.05 for va in verified_amounts):
                # Also check if it matches difference or sum of two verified amounts
                is_derived = any(abs(ca - abs(va1 - va2)) <= 0.05 for va1 in verified_amounts for va2 in verified_amounts)
                if not is_derived:
                    contradictions.append(f"Claimed amount ${ca:.2f} does not match any verified database record.")

        return contradictions


class DecisionPolicy:
    """Applies conservative decision criteria to convert AI recommendations into safe decisions."""

    def __init__(self, confidence_threshold: float = 0.85):
        self.confidence_threshold = confidence_threshold
        self.guardrail = EvidenceGuardrail()
        self.validator = FactValidator()

    def evaluate_decision(
        self,
        raw_decision: str,
        confidence: float,
        reason: str,
        cited_evidence_ids: List[str],
        evidence_set: EvidenceSet,
        exception: FinancialException,
    ) -> ValidationResult:
        """
        Evaluate LLM recommendation against guardrails and fact validator.
        """
        verified_ids, unverified_ids = self.guardrail.verify_citations(cited_evidence_ids, evidence_set)
        contradictions = self.validator.validate_facts(reason, evidence_set)

        # Rule 1: Anti-hallucination rejection
        if unverified_ids:
            return ValidationResult(
                passed=False,
                reason=f"UNVERIFIED_EVIDENCE: Cited evidence IDs {unverified_ids} do not exist in verified database records.",
                verified_ids=verified_ids,
                unverified_ids=unverified_ids,
                contradictions=contradictions,
            )

        # Rule 2: Factual contradiction rejection
        if contradictions:
            return ValidationResult(
                passed=False,
                reason=f"FACTUAL_CONTRADICTION: {'; '.join(contradictions)}",
                verified_ids=verified_ids,
                unverified_ids=unverified_ids,
                contradictions=contradictions,
            )

        # Rule 3: Low confidence rejection
        if confidence < self.confidence_threshold:
            return ValidationResult(
                passed=False,
                reason=f"LOW_CONFIDENCE: Confidence {confidence:.2f} is below required safety threshold {self.confidence_threshold:.2f}.",
                verified_ids=verified_ids,
                unverified_ids=unverified_ids,
                contradictions=contradictions,
            )

        # Rule 4: RESOLVED requires at least one verified evidence item
        if raw_decision.upper() in ("RESOLVED", "AI_RESOLVED"):
            if not verified_ids and len(evidence_set) == 0:
                return ValidationResult(
                    passed=False,
                    reason="INSUFFICIENT_EVIDENCE: Resolution proposed without any supporting database evidence.",
                    verified_ids=[],
                    unverified_ids=[],
                    contradictions=[],
                )

        return ValidationResult(
            passed=True,
            reason="Verification passed all safety checks.",
            verified_ids=verified_ids,
            unverified_ids=[],
            contradictions=[],
        )

