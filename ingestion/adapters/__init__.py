"""
Source Adapters for VaultRecon AI.
"""

from ingestion.adapters.base import BaseSourceAdapter, NormalizedDataset
from ingestion.adapters.generic_csv import GenericCSVAdapter

__all__ = [
    "BaseSourceAdapter",
    "NormalizedDataset",
    "GenericCSVAdapter",
]

