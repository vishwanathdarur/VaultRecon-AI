"""
ReconRiver External Validation Benchmark Runner for VaultRecon AI.
Evaluates the generalized VaultRecon AI system against the external ReconRiver dataset.
"""

import os
import time
import shutil
import argparse
from typing import Dict, Any, List, Optional
import numpy as np
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from recon.storage import MiniVaultDBClient
from recon.rules import ReconciliationRules
from recon.matcher import ReconciliationEngine
from ingestion.adapters.reconriver import ReconRiverAdapter
from ingestion.loader import IngestionLoader
from ai.agent import AIController
from ai.llm import get_llm_provider


def run_reconriver_benchmark(dataset_dir: str, scenario_name: str, db_dir: str = "./data_vault_reconriver_bench", provider: Optional[str] = None):
    console = Console()
    console.print(Panel(f"[bold cyan]VaultRecon AI Generalized Evaluation: ReconRiver ({scenario_name})[/bold cyan]", expand=False))

    # 1. Load using ReconRiverAdapter
    adapter = ReconRiverAdapter(dataset_dir)
    dataset = adapter.load_dataset()

    console.print(f"Loaded: [green]{len(dataset.payments)} Payments[/green], [cyan]{len(dataset.invoices)} Invoices[/cyan], [blue]{len(dataset.processor_transactions)} Processor Txns[/blue], [magenta]{len(dataset.batches)} Settlement Batches[/magenta], [yellow]{len(dataset.bank_transactions)} Bank Deposits[/yellow], [red]{len(dataset.refunds)} Refunds[/red], [bold]{len(dataset.ground_truth)} Ground Truth cases[/bold]")

    if dataset.schema_failures:
        console.print(f"[bold yellow]⚠️ Quarantined {len(dataset.schema_failures)} malformed raw rows during ingestion.[/bold yellow]")

    # 2. Ingest into MiniVaultDB
    shutil.rmtree(db_dir, ignore_errors=True)
    with MiniVaultDBClient(db_dir=db_dir, memtable_bytes=32 * 1024 * 1024) as db:
        loader = IngestionLoader(db)
        ingest_report = loader.load_dataset(dataset)

        # Register dataset's fee policy into engine rules
        rules = ReconciliationRules()
        for p in dataset.fee_policies:
            rules.fee_registry.register(p)

        # 3. Run Generalized Reconciliation Engine
        engine = ReconciliationEngine(db, rules=rules)
        latencies_ms = []

        for pay in dataset.payments:
            t0 = time.perf_counter()
            engine.reconcile_order(pay)
            t1 = time.perf_counter()
            latencies_ms.append((t1 - t0) * 1000.0)

        matcher_report = engine.reconcile_all(dataset.payments)

        # 4. Run AI Controller on Exceptions
        llm = get_llm_provider(provider)
        ai_controller = AIController(db, llm_provider=llm, fee_registry=rules.fee_registry)
        investigated_exceptions = []
        for exc in matcher_report.exceptions:
            ai_controller.investigate(exc)
            investigated_exceptions.append(exc)

    shutil.rmtree(db_dir, ignore_errors=True)

    # 5. Evaluate Against ReconRiver Ground Truth
    order_gt = [gt for gt in dataset.ground_truth if gt.get("result_scope") == "ORDER"]
    settlement_gt = [gt for gt in dataset.ground_truth if gt.get("result_scope") == "SETTLEMENT"]

    matched_order_keys = {m.work_key: m for m in matcher_report.order_matches}
    matched_batch_keys = {m.work_key: m for m in matcher_report.batch_matches}

    exc_by_work_key = {}
    for e in investigated_exceptions:
        exc_by_work_key[e.primary_record_id] = e
        for r_id in e.related_record_ids:
            exc_by_work_key[r_id] = e

    # Order-scope Evaluation
    tp_order = 0
    fp_order = 0
    fn_order = 0
    tn_order = 0
    order_logic_diffs = []

    for gt in order_gt:
        work_key = gt["work_key"]
        expected_outcome = gt["expected_outcome"]
        is_pred_match = work_key in matched_order_keys

        if expected_outcome == "MATCHED":
            if is_pred_match:
                tp_order += 1
            else:
                fn_order += 1
                pred_exc = exc_by_work_key.get(work_key)
                order_logic_diffs.append({
                    "work_key": work_key,
                    "expected": expected_outcome,
                    "predicted": pred_exc.exception_type if pred_exc else "EXCEPTION",
                    "reason": gt.get("explanation", ""),
                })
        else:
            if not is_pred_match:
                tn_order += 1
            else:
                fp_order += 1
                order_logic_diffs.append({
                    "work_key": work_key,
                    "expected": expected_outcome,
                    "predicted": "MATCHED",
                    "reason": gt.get("explanation", ""),
                })

    # Batch Settlement-scope Evaluation
    tp_batch = 0
    fp_batch = 0
    fn_batch = 0
    tn_batch = 0

    for gt in settlement_gt:
        work_key = gt["work_key"]
        expected_outcome = gt["expected_outcome"]
        is_pred_match = work_key in matched_batch_keys

        if expected_outcome == "MATCHED":
            if is_pred_match:
                tp_batch += 1
            else:
                fn_batch += 1
        else:
            if not is_pred_match:
                tn_batch += 1
            else:
                fp_batch += 1

    # Total Combined Metrics
    tot_eval = len(order_gt) + len(settlement_gt)
    tot_tp = tp_order + tp_batch
    tot_tn = tn_order + tn_batch
    tot_fp = fp_order + fp_batch
    tot_fn = fn_order + fn_batch

    precision = tot_tp / (tot_tp + tot_fp) if (tot_tp + tot_fp) > 0 else 0.0
    recall = tot_tp / (tot_tp + tot_fn) if (tot_tp + tot_fn) > 0 else 0.0
    accuracy = (tot_tp + tot_tn) / tot_eval if tot_eval > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    p50 = float(np.percentile(latencies_ms, 50)) if latencies_ms else 0.0
    p95 = float(np.percentile(latencies_ms, 95)) if latencies_ms else 0.0

    table = Table(title=f"ReconRiver Benchmark Results: {scenario_name}", show_header=True, header_style="bold magenta")
    table.add_column("Evaluation Metric", style="bold cyan")
    table.add_column("Order Scope", justify="right", style="white")
    table.add_column("Batch Scope", justify="right", style="white")
    table.add_column("Combined Total", justify="right", style="bold green")

    table.add_row("Evaluated Ground Truth Cases", f"{len(order_gt):,}", f"{len(settlement_gt):,}", f"{tot_eval:,}")
    table.add_row("True Positives (TP)", f"{tp_order}", f"{tp_batch}", f"[green]{tot_tp}[/green]")
    table.add_row("True Negatives (TN)", f"{tn_order}", f"{tn_batch}", f"[green]{tot_tn}[/green]")
    table.add_row("False Positives (FP)", f"{fp_order}", f"{fp_batch}", f"[red]{tot_fp}[/red]")
    table.add_row("False Negatives (FN)", f"{fn_order}", f"{fn_batch}", f"[yellow]{tot_fn}[/yellow]")
    table.add_row("Precision", f"{tp_order/(tp_order+fp_order)*100 if (tp_order+fp_order)>0 else 0:.2f}%", f"{tp_batch/(tp_batch+fp_batch)*100 if (tp_batch+fp_batch)>0 else 0:.2f}%", f"{precision*100:.2f}%")
    table.add_row("Recall", f"{tp_order/(tp_order+fn_order)*100 if (tp_order+fn_order)>0 else 0:.2f}%", f"{tp_batch/(tp_batch+fn_batch)*100 if (tp_batch+fn_batch)>0 else 0:.2f}%", f"{recall*100:.2f}%")
    table.add_row("Accuracy", f"{(tp_order+tn_order)/len(order_gt)*100 if len(order_gt)>0 else 0:.2f}%", f"{(tp_batch+tn_batch)/len(settlement_gt)*100 if len(settlement_gt)>0 else 0:.2f}%", f"[bold green]{accuracy*100:.2f}%[/bold green]")
    table.add_row("F1-Score", "-", "-", f"{f1*100:.2f}%")
    table.add_row("Unresolved Cases", f"{fn_order}", f"{fn_batch}", f"{tot_fn}")
    table.add_row("Ingestion Throughput", "-", "-", f"{ingest_report.throughput_records_per_sec:,.1f} rec/s")
    table.add_row("Recon Engine Throughput", "-", "-", f"{matcher_report.throughput_records_per_sec:,.1f} cases/s")
    table.add_row("P50 Lookup Latency", "-", "-", f"{p50:.4f} ms")
    table.add_row("P95 Lookup Latency", "-", "-", f"{p95:.4f} ms")

    console.print(table)
    return {
        "scenario": scenario_name,
        "tot_eval": tot_eval,
        "tp": tot_tp,
        "tn": tot_tn,
        "fp": tot_fp,
        "fn": tot_fn,
        "precision": precision,
        "recall": recall,
        "accuracy": accuracy,
        "f1": f1,
        "p50_ms": p50,
        "p95_ms": p95,
        "ingest_throughput": ingest_report.throughput_records_per_sec,
        "recon_throughput": matcher_report.throughput_records_per_sec,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ReconRiver Validation Benchmark Runner")
    parser.add_argument("--scenario", type=str, default="all", choices=["clean", "mixed", "all"])
    parser.add_argument("--provider", type=str, default=None, help="LLM Provider (mock, gemini, openai)")
    args = parser.parse_args()

    current_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.join(current_dir, "generated")
    if not os.path.exists(base_dir):
        base_dir = "datasets/external/reconriver/generated"

    if args.scenario in ("clean", "all"):
        run_reconriver_benchmark(os.path.join(base_dir, "clean-settlement"), "clean-settlement", provider=args.provider)
    if args.scenario in ("mixed", "all"):
        run_reconriver_benchmark(os.path.join(base_dir, "mixed-exceptions"), "mixed-exceptions", provider=args.provider)

