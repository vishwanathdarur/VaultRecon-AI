"""
R3n0va Synthetic Accounting Dataset Runner and Benchmark for VaultRecon AI.
Executes:
Phase 1: Blind Ingestion & Multi-Source Reconciliation
Phase 2: Ground-Truth Comparison (reconciliation_match.csv, dq_issue_manifest.csv)
"""

import os
import csv
import time
import shutil
from typing import Dict, Any, List
import numpy as np
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from collections import Counter

from recon.storage import MiniVaultDBClient
from recon.rules import ReconciliationRules
from recon.matcher import ReconciliationEngine, ReconciliationMatch
from recon.exceptions import FinancialException
from ingestion.adapters.r3n0va import R3n0vaAdapter
from ingestion.loader import IngestionLoader
from ai.agent import AIController
from ai.llm import get_llm_provider


def run_r3n0va_test(dataset_dir: str = "datasets/external/r3n0va/data/samples", db_dir: str = "./testdb_r3n0va", provider: Optional[str] = None):
    console = Console()
    console.print(Panel("[bold cyan]VaultRecon AI — R3n0va External Accounting Dataset Validation[/bold cyan]", expand=False))

    shutil.rmtree(db_dir, ignore_errors=True)

    # =========================================================================
    # PHASE 1: BLIND INGESTION & RECONCILIATION (NO GROUND TRUTH ACCESSED)
    # =========================================================================
    if not os.path.exists(dataset_dir):
        # Resolve relative to current script
        alt_path = os.path.join(os.path.dirname(__file__), "data", "samples")
        if os.path.exists(alt_path):
            dataset_dir = alt_path

    adapter = R3n0vaAdapter(dataset_dir=dataset_dir)
    dataset = adapter.load_dataset()

    with MiniVaultDBClient(db_dir=db_dir, memtable_bytes=32 * 1024 * 1024) as db:
        loader = IngestionLoader(db)
        t_ingest_start = time.perf_counter()
        ingest_report = loader.load_dataset(dataset)
        t_ingest_end = time.perf_counter()
        ingest_duration = max(t_ingest_end - t_ingest_start, 1e-6)

        rules = ReconciliationRules()
        for p in dataset.fee_policies:
            rules.fee_registry.register(p)

        engine = ReconciliationEngine(db, rules=rules)

        # Level 1 Recon
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
        l1_duration = max(t_l1_end - t_l1_start, 1e-6)

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
    console.print("[bold green]PHASE 1: BLIND RECONCILIATION REPORT[/bold green]")
    console.print("=" * 70)
    console.print(f"[bold]Dataset Rows:[/bold]")
    console.print(f"  • business_invoice.csv: {len(dataset.invoices)} invoices")
    console.print(f"  • payment.csv: {len(dataset.payments)} payments")
    console.print(f"  • bank_transaction.csv: {len(dataset.bank_transactions)} bank records")
    console.print(f"  • Schema Failures: {len(dataset.schema_failures)}")
    console.print(f"  • MiniVaultDB Stored Records: {dataset.total_records}")

    console.print(f"\n[bold]Reconciliation Pipeline Output:[/bold]")
    console.print(f"  • Total Cases Evaluated: {len(dataset.payments)}")
    console.print(f"  • Matched: {len(l1_matches)}")
    console.print(f"  • Exceptions Generated: {len(l1_exceptions)}")
    unresolved_count = sum(1 for e in l1_exceptions if e.status == "HUMAN_REVIEW")
    ai_resolved_count = sum(1 for e in l1_exceptions if e.status == "AI_RESOLVED")
    console.print(f"  • AI Resolved: {ai_resolved_count}")
    console.print(f"  • Escalated to Human Review: {unresolved_count}")

    console.print(f"\n[bold]Performance Metrics:[/bold]")
    console.print(f"  • Ingestion Throughput: {len(dataset.payments) / ingest_duration:,.1f} records/sec ({ingest_duration:.3f} s)")
    console.print(f"  • Recon Throughput: {len(dataset.payments) / l1_duration:,.1f} cases/sec ({l1_duration:.3f} s)")
    console.print(f"  • P50 Lookup Latency: {np.percentile(l1_latencies_ms, 50):.4f} ms")
    console.print(f"  • P95 Lookup Latency: {np.percentile(l1_latencies_ms, 95):.4f} ms")

    # =========================================================================
    # PHASE 2: GROUND TRUTH COMPARISON
    # =========================================================================
    console.print("\n" + "=" * 70)
    console.print("[bold cyan]PHASE 2: GROUND TRUTH COMPARISON[/bold cyan]")
    console.print("=" * 70)

    gt_matches_path = os.path.join(dataset_dir, "reconciliation_match.csv")
    gt_dq_path = os.path.join(dataset_dir, "dq_issue_manifest.csv")

    gt_expected_matches = set()
    if os.path.exists(gt_matches_path):
        with open(gt_matches_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                p_id = row.get("payment_id")
                if p_id:
                    gt_expected_matches.add(p_id)

    gt_expected_dq = set()
    if os.path.exists(gt_dq_path):
        with open(gt_dq_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rec_id = row.get("record_id")
                if rec_id:
                    gt_expected_dq.add(rec_id)

    our_matched_ids = {m.work_key for m in l1_matches}
    our_exception_ids = {e.primary_record_id for e in l1_exceptions}

    all_evaluated_ids = {p.transaction_id for p in dataset.payments}
    tp = 0
    fp = 0
    fn = 0
    tn = 0

    for pid in all_evaluated_ids:
        is_gt_match = pid in gt_expected_matches
        is_our_match = pid in our_matched_ids

        if is_gt_match and is_our_match:
            tp += 1
        elif not is_gt_match and is_our_match:
            fp += 1
        elif is_gt_match and not is_our_match:
            fn += 1
        elif not is_gt_match and not is_our_match:
            tn += 1

    total_gt = len(all_evaluated_ids)
    accuracy = (tp + tn) / total_gt if total_gt > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    eval_table = Table(title="R3n0va External Validation Performance", header_style="bold magenta")
    eval_table.add_column("Metric", style="bold cyan", width=30)
    eval_table.add_column("VaultRecon AI Result", style="bold green", justify="right", width=25)

    eval_table.add_row("Total Evaluated Records", f"{total_gt}")
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
    parser = argparse.ArgumentParser(description="VaultRecon AI — R3n0va Accounting Dataset Runner")
    parser.add_argument("--dataset-dir", type=str, default="datasets/external/r3n0va/data/samples", help="Dataset directory")
    parser.add_argument("--db-dir", type=str, default="./testdb_r3n0va", help="MiniVaultDB directory")
    parser.add_argument("--provider", type=str, default=None, help="LLM Provider (mock, gemini, openai)")
    args = parser.parse_args()
    run_r3n0va_test(dataset_dir=args.dataset_dir, db_dir=args.db_dir, provider=args.provider)

