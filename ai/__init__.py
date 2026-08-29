"""
AI Controller module for VaultRecon AI.
"""

from ai.agent import AIController, AIDecisionResult
from ai.tools import InvestigationToolkit
from ai.llm import BaseLLMProvider, GeminiProvider, OpenAIProvider, MockLLMProvider, get_llm_provider
from ai.prompts import SYSTEM_PROMPT, INVESTIGATION_USER_PROMPT_TEMPLATE

__all__ = [
    "AIController",
    "AIDecisionResult",
    "InvestigationToolkit",
    "BaseLLMProvider",
    "GeminiProvider",
    "OpenAIProvider",
    "MockLLMProvider",
    "get_llm_provider",
    "SYSTEM_PROMPT",
    "INVESTIGATION_USER_PROMPT_TEMPLATE",
]

