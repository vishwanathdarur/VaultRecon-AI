"""
Configurable Fee Policies, Fuzzy Scoring, and Deterministic Staged Rules for VaultRecon AI.
Decouples matching strategies from hardcoded assumptions, supporting multi-pass
staged reconciliation (Exact, Timing, Tolerance, Fuzzy) across multiple topologies.
"""

import re
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from ingestion.schemas import FeePolicy


STOPWORDS = {
    "EFT", "PAD", "POS", "DEP", "CHQ", "ADP", "PPD", "INC", "LTD",
    "SVC", "PMT", "PAYMENT", "INVOICE", "THE", "OF", "AND", "CDA",
    "CANADA", "REF", "CORP", "LLC", "BANK"
}


def normalize_description(desc: str) -> str:
    """Normalize financial memo / narrative by stripping punctuation, numbers, and stopwords."""
    if not desc:
        return ""
    s = re.sub(r"[^A-Z0-9 ]", " ", str(desc).upper())
    s = re.sub(r"\b(REF|CHQ|INV|ORD|PAY)?\d+\b", " ", s)
    tokens = [t for t in s.split() if t not in STOPWORDS and len(t) > 2]
    return " ".join(tokens)


def calculate_description_similarity(a: str, b: str) -> float:
    """
    Calculate combined sequence ratio and token Jaccard overlap similarity score in [0.0, 1.0].
    """
    na, nb = normalize_description(a), normalize_description(b)
    if not na or not nb:
        return 0.0
    seq = SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(na.split()), set(nb.split())
    jac = len(ta & tb) / len(ta | tb) if (ta | tb) else 0.0
    return max(seq, jac)


@dataclass
class MatchCandidate:
    source_record_id: str
    target_record_id: str
    score: float
    match_strategy: str  # EXACT, TIMING, TOLERANCE, FUZZY
    amount_diff: float = 0.0
    date_diff_days: int = 0
    desc_similarity: float = 1.0
    evidence: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class FeeSchedule:
    rate_percent: float
    flat_fee: float = 0.0


STANDARD_FEE_SCHEDULES = {
    "UPI": FeeSchedule(rate_percent=0.0, flat_fee=0.0),
    "DEBIT_CARD": FeeSchedule(rate_percent=0.9, flat_fee=0.0),
    "CREDIT_CARD": FeeSchedule(rate_percent=2.0, flat_fee=0.0),
    "NET_BANKING": FeeSchedule(rate_percent=0.0, flat_fee=15.0),
}

SPECIAL_MERCHANT_FEE_RULES = {
    "RULE_INTL_CARD_3.5": {
        "description": "International card surcharge rule (3.5% fee instead of domestic 2.0%)",
        "override_rate": 3.5,
        "applies_to": ["CREDIT_CARD", "DEBIT_CARD", "INTERNATIONAL_CARD"],
    },
    "RULE_HIGH_VOLUME_DISCOUNT": {
        "description": "Tier 1 merchant volume discount (1.2% card fee)",
        "override_rate": 1.2,
        "applies_to": ["CREDIT_CARD"],
    },
}


class FeePolicyRegistry:
    def __init__(self, allow_global_fallback: bool = False):
        self.policies: Dict[str, FeePolicy] = {}
        self.allow_global_fallback = allow_global_fallback
        self._register_default_policies()

    def register(self, policy: FeePolicy):
        """Register or override a fee policy."""
        self.policies[policy.policy_id] = policy

    def get(self, policy_id: str) -> Optional[FeePolicy]:
        return self.policies.get(policy_id)

    def _register_default_policies(self):
        # 1. Stripe Standard Policy (2.90% + $0.30)
        self.register(FeePolicy(
            policy_id="STRIPE_STANDARD",
            name="Stripe Standard (2.9% + $0.30)",
            percentage_rate=2.90,
            fixed_charge=0.30,
            currency="USD",
        ))

        self.register(FeePolicy(
            policy_id="CARD_STANDARD_2.9",
            name="Standard Card Policy (2.9% + $0.30)",
            percentage_rate=2.90,
            fixed_charge=0.30,
            payment_method="CARD",
            currency="ANY",
        ))

        # 3. Indian Standard Gateway Policies (Razorpay / PayU style)
        self.register(FeePolicy(
            policy_id="UPI_STANDARD",
            name="UPI Standard (0%)",
            percentage_rate=0.0,
            fixed_charge=0.0,
            payment_method="UPI",
            currency="ANY",
        ))
        self.register(FeePolicy(
            policy_id="DEBIT_CARD_STANDARD",
            name="Debit Card Standard (0.9%)",
            percentage_rate=0.9,
            fixed_charge=0.0,
            payment_method="DEBIT_CARD",
            currency="INR",
        ))
        self.register(FeePolicy(
            policy_id="CREDIT_CARD_STANDARD",
            name="Domestic Credit Card (2.0%)",
            percentage_rate=2.0,
            fixed_charge=0.0,
            payment_method="CREDIT_CARD",
            currency="INR",
        ))
        self.register(FeePolicy(
            policy_id="NET_BANKING_STANDARD",
            name="Net Banking Flat Fee (₹15)",
            percentage_rate=0.0,
            fixed_charge=15.0,
            payment_method="NET_BANKING",
            currency="INR",
        ))

        # 4. Direct Banking & Corporate Wire Transfer Policies (0%)
        self.register(FeePolicy(
            policy_id="DIRECT_DEBIT_ZERO",
            name="Direct Debit Transfer (0%)",
            percentage_rate=0.0,
            fixed_charge=0.0,
            payment_method="DIRECT_DEBIT",
            currency="ANY",
        ))
        self.register(FeePolicy(
            policy_id="BANK_TRANSFER_ZERO",
            name="Bank Transfer / Wire (0%)",
            percentage_rate=0.0,
            fixed_charge=0.0,
            payment_method="BANK_TRANSFER",
            currency="ANY",
        ))
        self.register(FeePolicy(
            policy_id="CHEQUE_ZERO",
            name="Cheque Clearing (0%)",
            percentage_rate=0.0,
            fixed_charge=0.0,
            payment_method="CHEQUE",
            currency="ANY",
        ))
        self.register(FeePolicy(
            policy_id="SEPA_CREDIT_ZERO",
            name="SEPA Credit Transfer (0%)",
            percentage_rate=0.0,
            fixed_charge=0.0,
            payment_method="SEPA_CREDIT_TRANSFER",
            currency="ANY",
        ))

        # 5. Contractual & Exception Policies
        self.register(FeePolicy(
            policy_id="RULE_INTL_CARD_3.5",
            name="International Premium Card Surcharge (3.5%)",
            percentage_rate=3.5,
            fixed_charge=0.0,
            payment_method="INTERNATIONAL_CARD",
        ))
        self.register(FeePolicy(
            policy_id="RULE_HIGH_VOLUME_DISCOUNT",
            name="Tier 1 High Volume Discount (1.2%)",
            percentage_rate=1.2,
            fixed_charge=0.0,
        ))

    def match_policy(
        self,
        merchant_id: Optional[str] = None,
        processor: Optional[str] = None,
        payment_method: Optional[str] = None,
        currency: Optional[str] = None,
    ) -> Optional[FeePolicy]:
        """
        Find the most specific matching fee policy for a given transaction context.
        Returns None if no matching policy is configured (UNKNOWN policy).
        """
        policy_list = list(reversed(list(self.policies.values())))

        # 1. Exact Match: processor + payment_method + currency
        for p in policy_list:
            if processor and p.processor == processor and p.processor != "ANY":
                if payment_method and p.payment_method not in ("ANY", payment_method):
                    continue
                if currency and p.currency not in ("ANY", currency):
                    continue
                return p

        # 2. Payment Method + Specific Currency Match
        for p in policy_list:
            if payment_method and p.payment_method == payment_method and p.currency == currency:
                return p

        # 3. Payment Method Match (where p.currency is ANY)
        for p in policy_list:
            if payment_method and p.payment_method == payment_method:
                return p

        # 4. Processor Match
        for p in policy_list:
            if processor and p.processor == processor and p.processor != "ANY":
                return p

        if self.allow_global_fallback:
            return self.policies.get("DEFAULT_FALLBACK", None)

        return None

# Global default registry instance
GLOBAL_FEE_REGISTRY = FeePolicyRegistry()


class ReconciliationRules:
    def __init__(
        self,
        amount_tolerance: float = 0.01,
        timing_window_days: int = 5,
        tolerance_window_days: int = 7,
        fuzzy_threshold: float = 0.35,
        time_window_hours: float = 72.0,
        enable_fee_validation: bool = True,
        topology: str = "GATEWAY",  # GATEWAY, DIRECT_ACCOUNTING, BANK_GL
        fee_registry: Optional[FeePolicyRegistry] = None,
    ):
        self.amount_tolerance = amount_tolerance
        self.timing_window_days = timing_window_days
        self.tolerance_window_days = tolerance_window_days
        self.fuzzy_threshold = fuzzy_threshold
        self.time_window_seconds = time_window_hours * 3600
        self.enable_fee_validation = enable_fee_validation
        self.topology = topology
        self.fee_registry = fee_registry or GLOBAL_FEE_REGISTRY

    def compute_expected_fee(
        self,
        amount: float,
        payment_method: Optional[str] = None,
        processor: Optional[str] = None,
        currency: Optional[str] = None,
        merchant_id: Optional[str] = None,
        policy_id: Optional[str] = None,
    ) -> Optional[float]:
        """Compute expected fee using dynamic FeePolicyRegistry. Returns None if policy unknown."""
        if not self.enable_fee_validation or self.topology == "BANK_GL":
            return 0.0

        if policy_id:
            policy = self.fee_registry.get(policy_id)
            if policy is None:
                return None
            return policy.calculate_fee(amount)

        policy = self.fee_registry.match_policy(
            merchant_id=merchant_id,
            processor=processor,
            payment_method=payment_method,
            currency=currency,
        )
        if policy is None:
            return None
        return policy.calculate_fee(amount)

    def is_amount_matching(self, expected: float, actual: float, tolerance: Optional[float] = None) -> bool:
        """Check if amount matches within tolerance."""
        tol = tolerance if tolerance is not None else self.amount_tolerance
        return abs(expected - actual) <= tol + 1e-6

    def is_currency_matching(self, c1: str, c2: str) -> bool:
        """Check if ISO currencies are identical."""
        return c1.strip().upper() == c2.strip().upper()

    def is_within_time_window(self, t1: int, t2: int) -> bool:
        """Check if timestamps are within SLA settlement window (seconds)."""
        return abs(t1 - t2) <= self.time_window_seconds

    def is_within_days_window(self, t1: int, t2: int, max_days: int) -> bool:
        """Check if timestamps are within calendar day window."""
        delta_sec = abs(t1 - t2)
        return delta_sec <= (max_days * 86400)
