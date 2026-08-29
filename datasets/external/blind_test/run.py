"""
VaultRecon AI — Blind Test Validation Runner.
Executes the complete unmodified VaultRecon AI pipeline on the blind test dataset.
"""

import os
import sys
import time
import shutil
import json
from typing import Dict, Any, List
import numpy as np
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from recon.storage import MiniVaultDBClient
from recon.rules import ReconciliationRules
from recon.matcher import ReconciliationEngine, ReconciliationMatch
from recon.exceptions import FinancialException
from ingestion.adapters.blind_test import BlindTestAdapter
from ingestion.loader import IngestionLoader
from ai.agent import AIController
from ai.llm import get_llm_provider


def run_blind_test(dataset_dir: str = "datasets/external/blind_test", db_dir: str = "./testdb_blind", provider: Optional[str] = None):
    console = Console()
    console.print(Panel("[bold cyan]VaultRecon AI — Blind Test Execution[/bold cyan]", expand=False))

    shutil.rmtree(db_dir, ignore_errors=True)

    if not os.path.exists(dataset_dir):
        alt_path = os.path.dirname(os.path.abspath(__file__))
        if os.path.exists(alt_path):
            dataset_dir = alt_path

    # 1. Dataset Ingestion
    adapter = BlindTestAdapter(dataset_dir=dataset_dir)
    dataset = adapter.load_dataset()

    console.print(f"[bold]Dataset Raw Ingestion Counts:[/bold]")
    console.print(f"  • Orders / Invoices: {len(dataset.invoices)}")
    console.print(f"  • Payments: {len(dataset.payments)}")
    console.print(f"  • Processor Transactions: {len(dataset.processor_transactions)}")
    console.print(f"  • Bank Transactions: {len(dataset.bank_transactions)}")
    console.print(f"  • Refunds: {len(dataset.refunds)}")
    console.print(f"  • Settlement Batches Constructed: {len(dataset.batches)}")
    console.print(f"  • Total Normalized Records: {dataset.total_records}")
    if dataset.schema_failures:
        console.print(f"  [bold red]⚠️ Quarantined Schema Failures: {len(dataset.schema_failures)}[/bold red]")
        for sf in dataset.schema_failures:
            console.print(f"    - {sf}")

    # 2. MiniVaultDB Load
    with MiniVaultDBClient(db_dir=db_dir, memtable_bytes=32 * 1024 * 1024) as db:
        loader = IngestionLoader(db)
        t_ingest_start = time.perf_counter()
        ingest_report = loader.load_dataset(dataset)
        t_ingest_end = time.perf_counter()

        rules = ReconciliationRules()
        for p in dataset.fee_policies:
            rules.fee_registry.register(p)

        engine = ReconciliationEngine(db, rules=rules)

        # 3. Level 1 (Order Scope)
        l1_latencies_ms = []
        l1_matches: List[ReconciliationMatch] = []
        l1_exceptions: List[FinancialException] = []

        t_l1_start = time.perf_counter()
        for pay in dataset.payments:
            t0 = time.perf_counter()
            match_res, exc = engine.reconcile_order(pay)
            t1 = time.perf_counter()
            l1_latencies_ms.append((t1 - t0) * 1000.0)
            if match_res:
                l1_matches.append(match_res)
            if exc:
                l1_exceptions.append(exc)
        t_l1_end = time.perf_counter()

        # 4. Level 2 (Batch Scope)
        l2_latencies_ms = []
        l2_matches: List[ReconciliationMatch] = []
        l2_exceptions: List[FinancialException] = []

        t_l2_start = time.perf_counter()
        for batch in dataset.batches:
            t0 = time.perf_counter()
            match_res, exc = engine.reconcile_batch(batch)
            t1 = time.perf_counter()
            l2_latencies_ms.append((t1 - t0) * 1000.0)
            if match_res:
                l2_matches.append(match_res)
            if exc:
                l2_exceptions.append(exc)
        t_l2_end = time.perf_counter()

        # 5. AI Controller Investigation
        llm = get_llm_provider(provider)
        ai_controller = AIController(db, llm_provider=llm, fee_registry=rules.fee_registry)
        all_exceptions = l1_exceptions + l2_exceptions
        ai_latencies_ms = []
        for exc in all_exceptions:
            t0 = time.perf_counter()
            ai_controller.investigate(exc)
            t1 = time.perf_counter()
            ai_latencies_ms.append((t1 - t0) * 1000.0)

    shutil.rmtree(db_dir, ignore_errors=True)

    console.print("\n" + "=" * 70)
    console.print("[bold green]BLIND EXECUTION REPORT[/bold green]")
    console.print("=" * 70)
    console.print(f"[bold]Level 1 (Order Scope) Results:[/bold]")
    console.print(f"  • Total Orders Evaluated: {len(dataset.payments)}")
    console.print(f"  • Clean Deterministic Matches: {len(l1_matches)}")
    console.print(f"  • Exceptions Flagged: {len(l1_exceptions)}")

    console.print(f"\n[bold]Level 2 (Settlement Batch Scope) Results:[/bold]")
    console.print(f"  • Total Batches Evaluated: {len(dataset.batches)}")
    console.print(f"  • Matched Batches: {len(l2_matches)}")
    console.print(f"  • Batch Exceptions Flagged: {len(l2_exceptions)}")

    ai_resolved_count = sum(1 for e in all_exceptions if e.status == "AI_RESOLVED")
    human_review_count = sum(1 for e in all_exceptions if e.status == "HUMAN_REVIEW")

    console.print(f"\n[bold]AI Controller Decisions across {len(all_exceptions)} Exceptions:[/bold]")
    console.print(f"  • AI Resolved (Verified Contract / Surcharge): {ai_resolved_count}")
    console.print(f"  • Escalated to Human Review: {human_review_count}")

    # Telemetry
    ingest_dur = max(t_ingest_end - t_ingest_start, 1e-6)
    l1_dur = max(t_l1_end - t_l1_start, 1e-6)
    l2_dur = max(t_l2_end - t_l2_start, 1e-6)

    console.print(f"\n[bold]Performance & Latency Telemetry:[/bold]")
    console.print(f"  • Ingestion Throughput: {dataset.total_records / ingest_dur:,.1f} records/sec ({ingest_dur:.3f} s)")
    console.print(f"  • Level 1 Recon Throughput: {len(dataset.payments) / l1_dur:,.1f} orders/sec ({l1_dur:.3f} s)")
    console.print(f"  • Level 2 Recon Throughput: {len(dataset.batches) / l2_dur:,.1f} batches/sec ({l2_dur:.3f} s)")
    console.print(f"  • MiniVaultDB P50 Lookup Latency: {np.percentile(l1_latencies_ms, 50):.4f} ms")
    console.print(f"  • MiniVaultDB P95 Lookup Latency: {np.percentile(l1_latencies_ms, 95):.4f} ms")
    if ai_latencies_ms:
        console.print(f"  • AI Investigation P50 Latency: {np.percentile(ai_latencies_ms, 50):.2f} ms")
        console.print(f"  • AI Investigation P95 Latency: {np.percentile(ai_latencies_ms, 95):.2f} ms")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="VaultRecon AI — Blind Test Validation Runner")
    parser.add_argument("--dataset-dir", type=str, default="datasets/external/blind_test", help="Dataset directory")
    parser.add_argument("--db-dir", type=str, default="./testdb_blind", help="MiniVaultDB directory")
    parser.add_argument("--provider", type=str, default=None, help="LLM Provider (mock, gemini, openai)")
    args = parser.parse_args()
    run_blind_test(dataset_dir=args.dataset_dir, db_dir=args.db_dir, provider=args.provider)

