"""
VaultRecon AI — System Evaluation & Benchmark Suite.
Supports:
1. Razorpay Track 4 Multi-Topology Synthetic Evaluation (50, 100, 500, 1000 orders)
2. ReconRiver External Benchmark Validation
"""

import sys
import time
import shutil
import argparse
from typing import Dict, Any, List
import numpy as np
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from recon.storage import MiniVaultDBClient
from recon.rules import ReconciliationRules
from recon.matcher import ReconciliationEngine
from ingestion.adapters.razorpay import RazorpayStyleSyntheticAdapter
from ingestion.loader import IngestionLoader
from ai.agent import AIController
from ai.llm import get_llm_provider


def run_razorpay_suite(sizes: List[int] = [50, 100, 500, 1000], db_dir: str = "./data_vault_eval"):
    console = Console()
    console.print(Panel("[bold cyan]VaultRecon AI — Razorpay Track 4 Multi-Level Reconciliation Benchmark[/bold cyan]", expand=False))

    results_table = Table(title="Razorpay Track 4 Multi-Level Benchmark Results", header_style="bold magenta")
    results_table.add_column("Order Scale", justify="right", style="bold cyan")
    results_table.add_column("Records Ingested", justify="right", style="white")
    results_table.add_column("Order Level (Match / Total)", justify="right", style="green")
    results_table.add_column("Batch Level (Match / Total)", justify="right", style="green")
    results_table.add_column("Order Acc", justify="right", style="bold green")
    results_table.add_column("Batch Acc", justify="right", style="bold green")
    results_table.add_column("Overall Acc (Combined Total)", justify="right", style="bold yellow")
    results_table.add_column("Precision", justify="right", style="white")
    results_table.add_column("Recall", justify="right", style="white")
    results_table.add_column("Ingest (rec/s)", justify="right", style="white")
    results_table.add_column("Recon (cases/s)", justify="right", style="white")
    results_table.add_column("P50 (ms)", justify="right", style="white")
    results_table.add_column("P95 (ms)", justify="right", style="white")

    for size in sizes:
        shutil.rmtree(db_dir, ignore_errors=True)
        adapter = RazorpayStyleSyntheticAdapter(count=size, seed=42, batch_size=10, exception_rate=0.20)
        dataset = adapter.load_dataset()

        with MiniVaultDBClient(db_dir=db_dir, memtable_bytes=32 * 1024 * 1024) as db:
            loader = IngestionLoader(db)
            ingest_report = loader.load_dataset(dataset)

            rules = ReconciliationRules()
            for p in dataset.fee_policies:
                rules.fee_registry.register(p)

            engine = ReconciliationEngine(db, rules=rules)
            latencies_ms = []

            for pay in dataset.payments:
                t0 = time.perf_counter()
                engine.reconcile_order(pay)
                t1 = time.perf_counter()
                latencies_ms.append((t1 - t0) * 1000.0)

            matcher_report = engine.reconcile_all(dataset.payments)

            llm = get_llm_provider()
            ai_controller = AIController(db, llm_provider=llm, fee_registry=rules.fee_registry)
            for exc in matcher_report.exceptions:
                ai_controller.investigate(exc)

        shutil.rmtree(db_dir, ignore_errors=True)

        # Ground truth comparison
        order_gt = [gt for gt in dataset.ground_truth if gt.get("result_scope") == "ORDER"]
        batch_gt = [gt for gt in dataset.ground_truth if gt.get("result_scope") == "SETTLEMENT"]

        matched_orders = {m.work_key: m for m in matcher_report.order_matches}
        matched_batches = {m.work_key: m for m in matcher_report.batch_matches}

        # Level 1: Order-Level
        tp_ord = sum(1 for gt in order_gt if gt["expected_outcome"] == "MATCHED" and gt["work_key"] in matched_orders)
        tn_ord = sum(1 for gt in order_gt if gt["expected_outcome"] != "MATCHED" and gt["work_key"] not in matched_orders)
        fp_ord = sum(1 for gt in order_gt if gt["expected_outcome"] != "MATCHED" and gt["work_key"] in matched_orders)
        fn_ord = sum(1 for gt in order_gt if gt["expected_outcome"] == "MATCHED" and gt["work_key"] not in matched_orders)
        order_acc = (tp_ord + tn_ord) / len(order_gt) if order_gt else 0.0

        # Level 2: Batch-Level
        tp_batch = sum(1 for gt in batch_gt if gt["expected_outcome"] == "MATCHED" and gt["work_key"] in matched_batches)
        tn_batch = sum(1 for gt in batch_gt if gt["expected_outcome"] != "MATCHED" and gt["work_key"] not in matched_batches)
        fp_batch = sum(1 for gt in batch_gt if gt["expected_outcome"] != "MATCHED" and gt["work_key"] in matched_batches)
        fn_batch = sum(1 for gt in batch_gt if gt["expected_outcome"] == "MATCHED" and gt["work_key"] not in matched_batches)
        batch_acc = (tp_batch + tn_batch) / len(batch_gt) if batch_gt else 0.0

        # Combined Total
        tot_eval = len(order_gt) + len(batch_gt)
        tot_tp = tp_ord + tp_batch
        tot_tn = tn_ord + tn_batch
        tot_fp = fp_ord + fp_batch
        tot_fn = fn_ord + fn_batch

        overall_acc = (tot_tp + tot_tn) / tot_eval if tot_eval > 0 else 0.0
        precision = tot_tp / (tot_tp + tot_fp) if (tot_tp + tot_fp) > 0 else 0.0
        recall = tot_tp / (tot_tp + tot_fn) if (tot_tp + tot_fn) > 0 else 0.0
        p50 = float(np.percentile(latencies_ms, 50)) if latencies_ms else 0.0
        p95 = float(np.percentile(latencies_ms, 95)) if latencies_ms else 0.0

        results_table.add_row(
            f"{size} orders",
            f"{dataset.total_records:,}",
            f"{tp_ord}/{len(order_gt)}",
            f"{tp_batch}/{len(batch_gt)}",
            f"{order_acc*100:.2f}%",
            f"{batch_acc*100:.2f}%",
            f"{overall_acc*100:.2f}% ({tot_tp+tot_tn}/{tot_eval})",
            f"{precision*100:.2f}%",
            f"{recall*100:.2f}%",
            f"{ingest_report.throughput_records_per_sec:,.1f}",
            f"{matcher_report.throughput_records_per_sec:,.1f}",
            f"{p50:.4f}",
            f"{p95:.4f}",
        )

    console.print(results_table)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VaultRecon AI Suite Runner")
    parser.add_argument("--sizes", nargs="+", type=int, default=[50, 100, 500, 1000])
    args = parser.parse_args()
    run_razorpay_suite(args.sizes)
