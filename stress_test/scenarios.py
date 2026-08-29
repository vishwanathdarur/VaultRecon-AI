"""
Scenario Definitions and Proportions for VaultRecon AI Stress Testing.
Defines 22 distinct financial reconciliation scenarios across standard matches,
timing/tolerance edge cases, operational exceptions, and adversarial AI safety tests.
"""

from enum import Enum
from typing import Dict, Any, List


class ScenarioType(str, Enum):
    # Standard & Staged Matches (Deterministic True Positives)
    EXACT_MATCH = "EXACT_MATCH"
    TIMING_MATCH = "TIMING_MATCH"
    TOLERANCE_MATCH = "TOLERANCE_MATCH"
    FUZZY_DESCRIPTION_MATCH = "FUZZY_DESCRIPTION_MATCH"
    PARTIAL_PAYMENT = "PARTIAL_PAYMENT"

    # Contractual / Resolvable Discrepancies (AI True Positives)
    FEE_MISMATCH_RESOLVABLE = "FEE_MISMATCH_RESOLVABLE"
    BUNDLED_PAYMENT_RESOLVABLE = "BUNDLED_PAYMENT_RESOLVABLE"

    # Operational Exceptions (Deterministic & AI True Negatives)
    FEE_MISMATCH_UNRESOLVABLE = "FEE_MISMATCH_UNRESOLVABLE"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    MISSING_PROCESSOR = "MISSING_PROCESSOR"
    MISSING_INTERNAL = "MISSING_INTERNAL"
    DUPLICATE_PROCESSOR = "DUPLICATE_PROCESSOR"
    DUPLICATE_INTERNAL = "DUPLICATE_INTERNAL"
    PARTIAL_REFUND = "PARTIAL_REFUND"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    LATE_SETTLEMENT = "LATE_SETTLEMENT"
    MISSING_BANK_DEPOSIT = "MISSING_BANK_DEPOSIT"
    UNKNOWN_FEE_POLICY = "UNKNOWN_FEE_POLICY"
    BUNDLED_PAYMENT_AMBIGUOUS = "BUNDLED_PAYMENT_AMBIGUOUS"

    # Adversarial AI Safety Scenarios
    ADVERSARIAL_PROMPT_INJECTION = "ADVERSARIAL_PROMPT_INJECTION"
    ADVERSARIAL_HALLUCINATED_ID = "ADVERSARIAL_HALLUCINATED_ID"
    ADVERSARIAL_CONTRADICTION = "ADVERSARIAL_CONTRADICTION"


# Target weight distribution for 10,000 cases
SCENARIO_WEIGHTS: Dict[ScenarioType, float] = {
    # 55% Clean / Deterministic Matches
    ScenarioType.EXACT_MATCH: 0.35,
    ScenarioType.TIMING_MATCH: 0.10,
    ScenarioType.TOLERANCE_MATCH: 0.04,
    ScenarioType.FUZZY_DESCRIPTION_MATCH: 0.03,
    ScenarioType.PARTIAL_PAYMENT: 0.03,

    # 5% Resolvable AI Scenarios
    ScenarioType.FEE_MISMATCH_RESOLVABLE: 0.03,
    ScenarioType.BUNDLED_PAYMENT_RESOLVABLE: 0.02,

    # 35% Genuine Operational Exceptions
    ScenarioType.FEE_MISMATCH_UNRESOLVABLE: 0.05,
    ScenarioType.AMOUNT_MISMATCH: 0.05,
    ScenarioType.MISSING_PROCESSOR: 0.04,
    ScenarioType.MISSING_INTERNAL: 0.04,
    ScenarioType.DUPLICATE_PROCESSOR: 0.03,
    ScenarioType.DUPLICATE_INTERNAL: 0.03,
    ScenarioType.PARTIAL_REFUND: 0.03,
    ScenarioType.CURRENCY_MISMATCH: 0.02,
    ScenarioType.LATE_SETTLEMENT: 0.02,
    ScenarioType.MISSING_BANK_DEPOSIT: 0.02,
    ScenarioType.UNKNOWN_FEE_POLICY: 0.01,
    ScenarioType.BUNDLED_PAYMENT_AMBIGUOUS: 0.01,

    # 5% Adversarial AI Safety Tests
    ScenarioType.ADVERSARIAL_PROMPT_INJECTION: 0.02,
    ScenarioType.ADVERSARIAL_HALLUCINATED_ID: 0.02,
    ScenarioType.ADVERSARIAL_CONTRADICTION: 0.01,
}

