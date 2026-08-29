"""
Hidden Ground Truth Representation for VaultRecon AI Stress Testing.
Defines expected deterministic reconciliation outcomes, exception types, and AI decisions.
"""

import json
import os
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from stress_test.scenarios import ScenarioType


class GroundTruthRecord(BaseModel):
    case_id: str
    scenario_type: ScenarioType
    primary_record_id: str
    order_id: str
    expected_recon_outcome: str  # MATCHED or EXCEPTION
    expected_exception_type: Optional[str] = None
    expected_ai_decision: Optional[str] = None  # AI_RESOLVED or HUMAN_REVIEW
    is_true_positive: bool = True  # True = valid financial match, False = genuine anomaly
    amount: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GroundTruthDataset(BaseModel):
    total_cases: int
    cases: Dict[str, GroundTruthRecord] = Field(default_factory=dict)

    def save_json(self, file_path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))

    @classmethod
    def load_json(cls, file_path: str) -> "GroundTruthDataset":
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return cls.model_validate(data)

