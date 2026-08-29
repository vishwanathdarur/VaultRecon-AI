"""
Source Adapters for VaultRecon AI.
"""

from ingestion.adapters.base import BaseSourceAdapter, NormalizedDataset
from ingestion.adapters.reconriver import ReconRiverAdapter
from ingestion.adapters.razorpay import RazorpayStyleSyntheticAdapter
from ingestion.adapters.generic_csv import GenericCSVAdapter
from ingestion.adapters.blind_test import BlindTestAdapter
from ingestion.adapters.r3n0va import R3n0vaAdapter
from ingestion.adapters.bank_gl import BankGLAdapter
from ingestion.adapters.invoice_matcher import InvoiceMatcherAdapter

__all__ = [
    "BaseSourceAdapter",
    "NormalizedDataset",
    "ReconRiverAdapter",
    "RazorpayStyleSyntheticAdapter",
    "GenericCSVAdapter",
    "BlindTestAdapter",
    "R3n0vaAdapter",
    "BankGLAdapter",
    "InvoiceMatcherAdapter",
]

