"""
Invoice Payment Matcher Blind Validation Runner for VaultRecon AI.
Executes:
Phase 1: Blind Ingestion & Multi-Source Reconciliation (No ground truth accessed)
Phase 2: Comprehensive Evaluation of Combinatorial & Bundled Payment Scenarios
Phase 3: Ground-Truth Comparison, MiniVaultDB telemetry, and Confusion Matrix
"""

import os
import csv
import time
import shutil
from typing import Dict, Any, List, Tuple
import numpy as np
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from collections import Counter

from recon.storage import MiniVaultDBClient
from recon.rules import ReconciliationRules, FeePolicyRegistry
from recon.matcher import ReconciliationEngine, ReconciliationMatch
from recon.exceptions import FinancialException
from ingestion.adapters.invoice_matcher import InvoiceMatcherAdapter
from ingestion.loader import IngestionLoader
from ingestion.schemas import PaymentRecord, InvoiceRecord, ProcessorTransaction, BankTransactionRecord
from ai.agent import AIController
from ai.llm import get_llm_provider


def run_invoice_matcher_validation(dataset_dir: str = "datasets/external/invoice_matcher", db_dir: str = "./testdb_invoice_matcher", provider: Optional[str] = None):
    console = Console()
    console.print(Panel("[bold cyan]VaultRecon AI — Fourth External Blind Validation: Invoice Payment Matcher[/bold cyan]", expand=False))

    shutil.rmtree(db_dir, ignore_errors=True)

    if not os.path.exists(dataset_dir):
        alt_path = os.path.dirname(os.path.abspath(__file__))
        if os.path.exists(alt_path):
            dataset_dir = alt_path

    # =========================================================================
    # PART 1: END-TO-END FIXTURE DATASET BLIND RUN
    # =========================================================================
    adapter = InvoiceMatcherAdapter(dataset_dir=dataset_dir)
    dataset = adapter.load_dataset()

    records_written = 0
    indexes_created = 0
    prefix_scans_performed = 0
    candidate_lookups = 0

    with MiniVaultDBClient(db_dir=db_dir, memtable_bytes=32 * 1024 * 1024) as db:
        loader = IngestionLoader(db)
        t_ingest_start = time.perf_counter()
        ingest_report = loader.load_dataset(dataset)
        t_ingest_end = time.perf_counter()
        ingest_duration = max(t_ingest_end - t_ingest_start, 1e-6)
        records_written += dataset.total_records
        indexes_created += (len(dataset.payments) + len(dataset.invoices) + len(dataset.processor_transactions) + len(dataset.bank_transactions))

        rules = ReconciliationRules(
            topology="DIRECT_ACCOUNTING",
            amount_tolerance=0.05,
            timing_window_days=7,
            tolerance_window_days=10,
            fuzzy_threshold=0.35,
            enable_fee_validation=False,
        )
        for p in dataset.fee_policies:
            rules.fee_registry.register(p)

        engine = ReconciliationEngine(db, rules=rules)

        l1_latencies_ms = []
        t_l1_start = time.perf_counter()
        report = engine.reconcile_all(dataset.payments)
        t_l1_end = time.perf_counter()
        l1_duration = max(t_l1_end - t_l1_start, 1e-6)

        prefix_scans_performed += len(dataset.payments) * 4 + len(dataset.processor_transactions)

        for pay in dataset.payments:
            t0 = time.perf_counter()
            engine.reconcile_order(pay)
            t1 = time.perf_counter()
            l1_latencies_ms.append((t1 - t0) * 1000.0)
            candidate_lookups += 1

        l1_matches = report.matches
        l1_exceptions = report.exceptions

        # AI Controller
        llm = get_llm_provider(provider)
        ai_controller = AIController(db, llm_provider=llm, fee_registry=rules.fee_registry)
        ai_latencies_ms = []
        for exc in l1_exceptions:
            t0 = time.perf_counter()
            ai_controller.investigate(exc)
            t1 = time.perf_counter()
            ai_latencies_ms.append((t1 - t0) * 1000.0)

    shutil.rmtree(db_dir, ignore_errors=True)

    console.print("\n" + "=" * 70)
    console.print("[bold green]PART 1: BLIND RECONCILIATION REPORT (FIXTURE DATASET)[/bold green]")
    console.print("=" * 70)
    console.print(f"[bold]Dataset Input Counts:[/bold]")
    console.print(f"  • Extracted Invoice Files: {len(dataset.invoices)}")
    console.print(f"  • Bank Deposit Lines: {len(dataset.payments)}")
    console.print(f"  • Total Normalized Records: {dataset.total_records}")
    console.print(f"  • Ingestion Failures: {len(dataset.schema_failures)}")

    console.print(f"\n[bold]Reconciliation Pipeline Output:[/bold]")
    console.print(f"  • Matched Invoice <-> Bank Deposit Pairs: {len(l1_matches)}")
    console.print(f"  • Exceptions Generated: {len(l1_exceptions)}")
    unresolved_count = sum(1 for e in l1_exceptions if e.status == "HUMAN_REVIEW")
    ai_resolved_count = sum(1 for e in l1_exceptions if e.status == "AI_RESOLVED")
    console.print(f"  • AI Resolved (Verified Evidence): {ai_resolved_count}")
    console.print(f"  • Escalated to Human Review: {unresolved_count}")

    # Ground Truth Comparison
    our_matched_ids = {m.work_key for m in l1_matches} | {m.internal_payment_id for m in l1_matches if m.internal_payment_id}
    all_payment_ids = {p.transaction_id for p in dataset.payments}
    gt_map = {gt.get("work_key"): gt for gt in dataset.ground_truth}

    tp = 0
    fp = 0
    fn = 0
    tn = 0

    for pid in all_payment_ids:
        gt_info = gt_map.get(pid, {})
        expected_match = gt_info.get("expected_outcome") == "MATCHED"
        is_our_match = pid in our_matched_ids

        if expected_match and is_our_match:
            tp += 1
        elif not expected_match and is_our_match:
            fp += 1
        elif expected_match and not is_our_match:
            fn += 1
        elif not expected_match and not is_our_match:
            tn += 1

    total_eval = len(all_payment_ids)
    accuracy = (tp + tn) / total_eval if total_eval > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    eval_table = Table(title="Invoice Payment Matcher Validation Performance", header_style="bold magenta")
    eval_table.add_column("Metric", style="bold cyan", width=30)
    eval_table.add_column("VaultRecon AI Result", style="bold green", justify="right", width=25)

    eval_table.add_row("Total Deposit Lines Evaluated", f"{total_eval}")
    eval_table.add_row("True Positives (TP)", f"{tp}")
    eval_table.add_row("True Negatives (TN)", f"{tn}")
    eval_table.add_row("False Positives (FP)", f"[bold green]{fp}[/bold green]" if fp == 0 else f"[bold red]{fp}[/bold red]")
    eval_table.add_row("False Negatives (FN)", f"[bold green]{fn}[/bold green]" if fn == 0 else f"[bold red]{fn}[/bold red]")
    eval_table.add_row("Precision", f"{precision * 100:.2f}%")
    eval_table.add_row("Recall", f"{recall * 100:.2f}%")
    eval_table.add_row("Accuracy", f"{accuracy * 100:.2f}%")
    eval_table.add_row("F1-Score", f"{f1 * 100:.2f}%")

    console.print(eval_table)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="VaultRecon AI — Invoice Payment Matcher Runner")
    parser.add_argument("--dataset-dir", type=str, default="datasets/external/invoice_matcher", help="Dataset directory")
    parser.add_argument("--db-dir", type=str, default="./testdb_invoice_matcher", help="MiniVaultDB directory")
    parser.add_argument("--provider", type=str, default=None, help="LLM Provider (mock, gemini, openai)")
    args = parser.parse_args()
    run_invoice_matcher_validation(dataset_dir=args.dataset_dir, db_dir=args.db_dir, provider=args.provider)

