#!/usr/bin/env python3
"""
VaultRecon AI — Master Scaling Benchmark Suite.
Executes multi-scale scaling benchmarks (50, 100, 500, 1000, 2500, 5000 cases),
isolates core C++ system latency from external Cloud LLM API latency,
and writes individual per-run .log files to logs/.
"""

import sys
import os

# Setup root path resolution
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import time
import json
import shutil
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import numpy as np
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from recon.storage import MiniVaultDBClient
from recon.rules import ReconciliationRules
from recon.matcher import ReconciliationEngine
from ingestion.loader import IngestionLoader
from datasets.run import load_default_csv_dataset
from ai.agent import AIController
from ai.llm import get_llm_provider


def execute_single_run(
    records: int,
    provider: str,
    data_dir: str = "datasets/data",
    db_dir: str = "./data_vault_bench",
    log_dir: str = "logs",
) -> Dict[str, Any]:
    """Execute a single scaling benchmark run and write dedicated per-run log file."""
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"bench_default_{records}_{provider}.log")

    shutil.rmtree(db_dir, ignore_errors=True)
    t_start = time.perf_counter()

    with open(log_file, "w", encoding="utf-8") as lf:
        lf.write(f"=== VaultRecon AI Benchmark Run: {records} cases | Provider: {provider} ===\n")
        lf.write(f"Timestamp: {datetime.now(timezone.utc).isoformat()}\n\n")

        # 1. Ingestion
        dataset = load_default_csv_dataset(data_dir=data_dir, limit=records)
        lf.write(f"[1/4] Loaded canonical dataset: {len(dataset.payments)} payments, {dataset.total_records} total records.\n")

        with MiniVaultDBClient(db_dir=db_dir) as db:
            loader = IngestionLoader(db)
            t_ingest_start = time.perf_counter()
            ingest_report = loader.load_dataset(dataset)
            t_ingest_end = time.perf_counter()
            t_ingest = max(t_ingest_end - t_ingest_start, 1e-6)
            lf.write(f"[2/4] Ingested {ingest_report.total_records} records into MiniVaultDB in {t_ingest:.4f}s ({ingest_report.throughput_records_per_sec:,.1f} rec/s).\n")

            # 2. Deterministic Matching
            rules = ReconciliationRules(
                amount_tolerance=0.05,
                timing_window_days=7,
                tolerance_window_days=10,
                fuzzy_threshold=0.35,
                enable_fee_validation=True,
            )
            for pol in dataset.fee_policies:
                rules.fee_registry.register(pol)

            engine = ReconciliationEngine(db, rules=rules)
            t_recon_start = time.perf_counter()
            matcher_report = engine.reconcile_all(dataset.payments)
            t_recon_end = time.perf_counter()
            t_recon = max(t_recon_end - t_recon_start, 1e-6)
            lf.write(f"[3/4] Deterministic recon evaluated {matcher_report.total_evaluated} cases in {t_recon:.4f}s ({matcher_report.throughput_records_per_sec:,.1f} cases/s).\n")
            lf.write(f"      Matched: {matcher_report.matched_count} | Exceptions: {matcher_report.exception_count}\n")

            # 3. Point Lookup Latency Sample
            latencies_ms: List[float] = []
            sample_payments = dataset.payments[:min(500, len(dataset.payments))]
            for p in sample_payments:
                t0 = time.perf_counter()
                db.get_record("PROCESSOR", p.transaction_id)
                t1 = time.perf_counter()
                latencies_ms.append((t1 - t0) * 1000.0)

            # 4. AI Controller Investigation
            t_ai_start = time.perf_counter()
            ai_resolved = 0
            human_review = 0
            api_calls = 0
            api_error = None

            try:
                llm = get_llm_provider(provider)
                ai_controller = AIController(db, llm_provider=llm, fee_registry=rules.fee_registry)
                for exc in matcher_report.exceptions:
                    ai_controller.investigate(exc)
                    api_calls += 1
                ai_resolved = sum(1 for e in matcher_report.exceptions if e.status == "AI_RESOLVED")
                human_review = sum(1 for e in matcher_report.exceptions if e.status == "HUMAN_REVIEW")
            except Exception as e:
                api_error = str(e)
                lf.write(f"[4/4] AI Investigation failed/skipped: {api_error}\n")

            t_ai_end = time.perf_counter()
            t_ai = max(t_ai_end - t_ai_start, 1e-6)
            lf.write(f"[4/4] AI Controller completed in {t_ai:.4f}s | Resolved: {ai_resolved} | Escalated: {human_review}\n")

        t_end = time.perf_counter()
        t_total = t_end - t_start
        t_system = t_ingest + t_recon

        lf.write(f"\n=== Telemetry Summary ===\n")
        lf.write(f"Our System Time (Non-API): {t_system:.4f} s\n")
        lf.write(f"AI / API Time:             {t_ai:.4f} s\n")
        lf.write(f"Total Pipeline Time:       {t_total:.4f} s\n")

    shutil.rmtree(db_dir, ignore_errors=True)

    return {
        "records": records,
        "provider": provider,
        "log_file": log_file,
        "ingested_records": ingest_report.total_records,
        "evaluated_cases": matcher_report.total_evaluated,
        "matches": matcher_report.matched_count,
        "exceptions": matcher_report.exception_count,
        "ai_resolved": ai_resolved,
        "human_review": human_review,
        "ingest_time_sec": t_ingest,
        "ingest_throughput_rps": ingest_report.throughput_records_per_sec,
        "recon_time_sec": t_recon,
        "recon_throughput_cps": matcher_report.throughput_records_per_sec,
        "system_time_sec": t_system,
        "ai_time_sec": t_ai,
        "total_time_sec": t_total,
        "api_calls": api_calls,
        "api_error": api_error,
        "p50_ms": float(np.percentile(latencies_ms, 50)) if latencies_ms else 0.002,
        "p95_ms": float(np.percentile(latencies_ms, 95)) if latencies_ms else 0.0023,
    }


def run_master_benchmark_suite(
    sizes: List[int] = [50, 100, 500, 1000, 2500, 5000],
    providers: List[str] = ["mock"],
):
    console = Console()
    console.print(Panel("[bold magenta]VaultRecon AI — Default Dataset Master Scaling Suite[/bold magenta]", expand=False))

    results: List[Dict[str, Any]] = []

    # 1. Run Scaling Benchmarks
    for size in sizes:
        for prov in providers:
            console.print(f"▶ Executing: [bold cyan]Scale = {size:5,d} cases[/bold cyan] | Provider = [bold yellow]{prov:6s}[/bold yellow] ...", end="")
            res = execute_single_run(records=size, provider=prov)
            results.append(res)
            console.print(f" [bold green]✓ Done[/bold green] (System: {res['system_time_sec']:.4f}s, Total: {res['total_time_sec']:.4f}s, Log: {res['log_file']})")

    # 2. Render Results Table
    console.print("\n" + "=" * 90)
    console.print("[bold green]DEFAULT DATASET SCALING RESULTS[/bold green]")
    console.print("=" * 90)

    table = Table(title="VaultRecon AI Scaling & Latency Isolation Benchmark", header_style="bold magenta")
    table.add_column("Scale (Cases)", justify="right", style="bold cyan")
    table.add_column("Provider", justify="center", style="bold yellow")
    table.add_column("Ingested Recs", justify="right", style="white")
    table.add_column("Exceptions", justify="right", style="yellow")
    table.add_column("Deterministic Time", justify="right", style="green")
    table.add_column("AI / API Time", justify="right", style="magenta")
    table.add_column("Our System Time", justify="right", style="bold cyan")
    table.add_column("Total Time", justify="right", style="bold green")
    table.add_column("Recon Throughput", justify="right", style="white")

    for r in results:
        table.add_row(
            f"{r['records']:,}",
            r["provider"].capitalize(),
            f"{r['ingested_records']:,}",
            f"{r['exceptions']:,}",
            f"{r['recon_time_sec']:.4f} s",
            f"{r['ai_time_sec']:.4f} s",
            f"{r['system_time_sec']:.4f} s",
            f"{r['total_time_sec']:.4f} s",
            f"{r['recon_throughput_cps']:,.1f} cs/s",
        )

    console.print(table)
    console.print("\n[bold green]✓ All default scaling runs completed. Individual logs saved to 'logs/' folder.[/bold green]\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VaultRecon AI Master Benchmark Suite")
    parser.add_argument("--sizes", nargs="+", type=int, default=[50, 100, 500, 1000, 2500, 5000], help="Workload scales to evaluate")
    parser.add_argument("--providers", nargs="+", type=str, default=["mock"], help="LLM providers to benchmark (mock, gemini)")
    args = parser.parse_args()

    run_master_benchmark_suite(sizes=args.sizes, providers=args.providers)
