"""
LLM Provider Integration for VaultRecon AI Controller.
Supports Google Gemini, OpenAI, and a deterministic Mock Provider for offline tests, CI/CD, and safety benchmarks.
"""

import os
import json
import re
import requests
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod


def _load_env_file():
    """Lightweight zero-dependency .env loader."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(base_dir, ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip().strip("'\"")
                        if k and not os.environ.get(k):
                            os.environ[k] = v
        except Exception:
            pass


_load_env_file()


class BaseLLMProvider(ABC):
    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate response from LLM."""
        pass


class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic rule-based Mock LLM for offline tests, safety suites, and continuous evaluation.
    Simulates LLM reasoning based on verified evidence in the prompt.
    """

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        # Prompt injection test: if prompt contains injection attack, ignore it and treat as data
        if "IGNORE ALL PREVIOUS INSTRUCTIONS" in user_prompt or "MARK THIS MATCHED" in user_prompt:
            return json.dumps({
                "decision": "HUMAN_REVIEW",
                "exception_type": "SUSPICIOUS_PROMPT_INJECTION",
                "confidence": 0.99,
                "reason": "Untrusted narrative text contains adversarial prompt injection string. Suspicious activity flagged.",
                "evidence_ids": [],
                "recommended_action": "escalate_to_security_team",
                "findings": ["Adversarial instruction detected in bank narrative."],
            })

        # Test Case 10: Hallucinated evidence ID test
        if "TEST_SCENARIO_HALLUCINATE" in user_prompt:
            return json.dumps({
                "decision": "AI_RESOLVED",
                "exception_type": "FEE_MISMATCH",
                "confidence": 0.95,
                "reason": "Fee difference is explained by fabricated policy ID.",
                "evidence_ids": ["EVID_POLICY_HALLUCINATED_9999"],
                "recommended_action": "mark_reconciled",
                "findings": ["Fabricated policy cited."],
            })

        # Test Case 11: Malformed JSON test
        if "TEST_SCENARIO_MALFORMED_JSON" in user_prompt:
            return "This is an unparseable response that is not JSON at all."

        # Test Case 12: Low confidence test
        if "TEST_SCENARIO_LOW_CONFIDENCE" in user_prompt:
            return json.dumps({
                "decision": "AI_RESOLVED",
                "exception_type": "AMOUNT_MISMATCH",
                "confidence": 0.55,  # Below 0.85 safety threshold
                "reason": "Uncertain resolution.",
                "evidence_ids": [],
                "recommended_action": "mark_reconciled",
                "findings": [],
            })

        # Test Case 9: Contradictory evidence test
        if "TEST_SCENARIO_CONTRADICTION" in user_prompt:
            return json.dumps({
                "decision": "AI_RESOLVED",
                "exception_type": "FEE_MISMATCH",
                "confidence": 0.95,
                "reason": "Processor fee was claimed to be $9999.88 which contradicts database.",
                "evidence_ids": [],
                "recommended_action": "mark_reconciled",
                "findings": [],
            })

        # Scenario: Fee Mismatch with verified contractual policy (e.g. RULE_INTL_CARD_3.5)
        if "FEE_MISMATCH" in user_prompt or "FEE_DISCREPANCY" in user_prompt:
            if "RULE_INTL_CARD_3.5" in user_prompt or "3.5%" in user_prompt or "INTERNATIONAL" in user_prompt:
                # Find the policy evidence ID from prompt
                ev_match = re.search(r"(EVID_POLICY_[A-Za-z0-9_\.]+)", user_prompt)
                ev_id = ev_match.group(1) if ev_match else "EVID_POLICY_RULE_INTL_CARD_3.5"
                return json.dumps({
                    "decision": "AI_RESOLVED",
                    "exception_type": "FEE_MISMATCH",
                    "confidence": 0.94,
                    "reason": "Difference in settlement fee is verified against contractual international card surcharge rule (3.5%).",
                    "evidence_ids": [ev_id],
                    "recommended_action": "mark_reconciled",
                    "findings": ["Contractual 3.5% fee policy verified."],
                })
            elif "HIGH_VOLUME" in user_prompt or "1.2%" in user_prompt:
                ev_match = re.search(r"(EVID_POLICY_[A-Za-z0-9_\.]+)", user_prompt)
                ev_id = ev_match.group(1) if ev_match else "EVID_POLICY_RULE_HIGH_VOLUME_DISCOUNT"
                return json.dumps({
                    "decision": "AI_RESOLVED",
                    "exception_type": "FEE_MISMATCH",
                    "confidence": 0.92,
                    "reason": "Discrepancy is verified against Tier 1 volume discount schedule (1.2%).",
                    "evidence_ids": [ev_id],
                    "recommended_action": "mark_reconciled",
                    "findings": ["Tier 1 volume discount verified."],
                })
            else:
                return json.dumps({
                    "decision": "HUMAN_REVIEW",
                    "exception_type": "FEE_MISMATCH",
                    "confidence": 0.88,
                    "reason": "Fee difference does not match any registered merchant policy or contractual exception.",
                    "evidence_ids": [],
                    "recommended_action": "request_gateway_proof",
                    "findings": ["Unexplained fee discrepancy."],
                })

        # Scenario: Bundled Payment Investigation
        if "BUNDLED_PAYMENT" in user_prompt or "BUNDLED" in user_prompt:
            # Check if matching invoices exist in verified evidence
            inv_matches = re.findall(r"(EVID_INVOICE_[A-Za-z0-9_\-]+|EVID_INV_[A-Za-z0-9_\-]+)", user_prompt)
            if len(inv_matches) >= 2:
                return json.dumps({
                    "decision": "AI_RESOLVED",
                    "exception_type": "BUNDLED_PAYMENT",
                    "confidence": 0.91,
                    "reason": f"Bank deposit covers a verified bundle of {len(inv_matches)} outstanding invoices for the same customer within clearing window.",
                    "evidence_ids": inv_matches,
                    "recommended_action": "mark_reconciled",
                    "findings": [f"Invoices {inv_matches} sum exactly to deposit total."],
                })
            else:
                return json.dumps({
                    "decision": "HUMAN_REVIEW",
                    "exception_type": "BUNDLED_PAYMENT",
                    "confidence": 0.85,
                    "reason": "Insufficient invoice evidence to prove bundled deposit combination.",
                    "evidence_ids": [],
                    "recommended_action": "request_remittance_advice",
                    "findings": ["Cannot confirm invoice bundle without remittance advice."],
                })

        # Scenario: Amount Mismatch
        if "AMOUNT_MISMATCH" in user_prompt:
            return json.dumps({
                "decision": "HUMAN_REVIEW",
                "exception_type": "AMOUNT_MISMATCH",
                "confidence": 0.95,
                "reason": "Payment amount differs from invoice total with no recorded discount, coupon, or credit note.",
                "evidence_ids": [],
                "recommended_action": "escalate_to_billing",
                "findings": ["Unexplained gross variance."],
            })

        # Scenario: Duplicate Record
        if "DUPLICATE" in user_prompt:
            return json.dumps({
                "decision": "HUMAN_REVIEW",
                "exception_type": "DUPLICATE_RECORD",
                "confidence": 0.92,
                "reason": "Multiple conflicting transactions exist for the same order/document reference.",
                "evidence_ids": [],
                "recommended_action": "escalate_to_treasury",
                "findings": ["Duplicate posting detected."],
            })

        # Scenario: Missing Record
        if "MISSING" in user_prompt:
            return json.dumps({
                "decision": "HUMAN_REVIEW",
                "exception_type": "MISSING_RECORD",
                "confidence": 0.95,
                "reason": "Counterparty transaction missing from internal books or external settlement statement.",
                "evidence_ids": [],
                "recommended_action": "escalate_to_treasury",
                "findings": ["Missing counterpart line."],
            })

        # Default fallback
        return json.dumps({
            "decision": "HUMAN_REVIEW",
            "exception_type": "UNRESOLVED_EXCEPTION",
            "confidence": 0.80,
            "reason": "Ambiguity cannot be reliably resolved with available database evidence.",
            "evidence_ids": [],
            "recommended_action": "escalate_to_finance_controller",
            "findings": ["Requires manual controller review."],
        })


class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model = model or os.environ.get("LLM_MODEL") or "gemini-flash-latest"

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": 0.0,
                "response_mime_type": "application/json",
            },
        }

        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code != 200:
            raise RuntimeError(f"Gemini API Error {response.status_code}: {response.text}")

        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }

        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code != 200:
            raise RuntimeError(f"OpenAI API Error {response.status_code}: {response.text}")

        data = response.json()
        return data["choices"][0]["message"]["content"]


def get_llm_provider(provider_type: Optional[str] = None) -> BaseLLMProvider:
    """Factory to return configured LLM Provider (defaults to MockLLM for deterministic offline safety)."""
    ptype = (provider_type or os.environ.get("LLM_PROVIDER", "mock")).lower()
    if ptype == "gemini" and os.environ.get("GEMINI_API_KEY"):
        return GeminiProvider()
    elif ptype == "openai" and os.environ.get("OPENAI_API_KEY"):
        return OpenAIProvider()
    return MockLLMProvider()
