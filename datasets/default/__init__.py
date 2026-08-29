"""
Default Demonstration Dataset Package for VaultRecon AI.
"""

from datasets.default.generator import DefaultDatasetGenerator
from datasets.default.run import run_default_pipeline

__all__ = [
    "DefaultDatasetGenerator",
    "run_default_pipeline",
]

