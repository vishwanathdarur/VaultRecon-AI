"""
VaultRecon AI Stress Test Benchmark Runner CLI.
Generates multi-source synthetic test cases, executes the full production pipeline,
and runs the independent ground-truth evaluator.
"""

import sys
import os
import argparse
import shutil
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from stress_test.generator import StressTestGenerator
from stress_test.runner import StressTestRunner
from stress_test.evaluator import StressTestEvaluator, EvaluationReport


def run_benchmark(count: int, seed: int = 20260825, save_dir: str = "stress_test/generated", provider: Optional[str] = None) -> EvaluationReport:
    console = Console()
    console.print(Panel(f"[bold magenta]VaultRecon AI — {count:,}-Case Adversarial Stress Testing Suite[/bold magenta]", expand=False))

    gt_file = os.path.join(save_dir, "ground_truth.json")

    # Step 1: Generate Dataset & Ground Truth
    console.print(f"[bold cyan][1/4] Generating {count:,} multi-source cases (Seed: {seed})...[/bold cyan]")
    generator = StressTestGenerator(seed=seed)
    dataset, ground_truth = generator.generate(total_cases=count)
    ground_truth.save_json(gt_file)
    console.print(f"  ✓ Ingestion records created: [bold]{dataset.total_records:,}[/bold]")
    console.print(f"  ✓ Hidden ground truth saved to: [dim]{gt_file}[/dim]")

    # Step 2: Run Production Pipeline
    console.print(f"\n[bold cyan][2/4] Executing production pipeline against MiniVaultDB...[/bold cyan]")
    runner = StressTestRunner(db_dir="./testdb_stress_runner", provider=provider)
    run_result = runner.run(dataset)

    console.print(f"  ✓ Ingestion throughput: [bold]{run_result.telemetry.ingestion_throughput_rps:,.1f} rec/s[/bold] ({run_result.telemetry.ingestion_duration_sec:.3f} s)")
    console.print(f"  ✓ Deterministic recon throughput: [bold]{run_result.telemetry.deterministic_throughput_cps:,.1f} cases/s[/bold] ({run_result.telemetry.deterministic_duration_sec:.3f} s)")
    console.print(f"  ✓ AI investigations conducted: [bold]{run_result.exception_count:,} exceptions[/bold] ({run_result.telemetry.ai_duration_sec:.3f} s)")
    console.print(f"  ✓ Total pipeline duration: [bold]{run_result.telemetry.total_pipeline_duration_sec:.3f} s[/bold]")

    # Step 3: Independent Evaluation against Ground Truth
    console.print(f"\n[bold cyan][3/4] Evaluating against hidden ground truth...[/bold cyan]")
    evaluator = StressTestEvaluator()
    report = evaluator.evaluate(run_result, ground_truth)
    json_path, md_path = evaluator.save_reports(report, output_dir=os.path.join(save_dir, "results"))

    # Step 4: Display Results Table
    console.print(f"\n[bold cyan][4/4] Evaluation Summary:[/bold cyan]")

    summary_table = Table(title=f"VaultRecon AI Stress Test Results ({count:,} Cases)", header_style="bold cyan")
    summary_table.add_column("Metric", style="bold white")
    summary_table.add_column("Value", style="bold")
    summary_table.add_column("Benchmark Target", style="dim")
    summary_table.add_column("Status", style="bold")

    acc_style = "green" if report.accuracy_pct >= 95.0 else "yellow"
    prec_style = "green" if report.precision_pct >= 98.0 else "yellow"
    rec_style = "green" if report.recall_pct >= 95.0 else "yellow"
    fmr_style = "green" if report.false_match_rate_pct <= 0.5 else "red"
    unsafe_style = "green" if report.unsafe_ai_resolutions == 0 else "bold red"

    summary_table.add_row("Overall Accuracy", f"[{acc_style}]{report.accuracy_pct:.2f}%[/{acc_style}]", ">= 95.00%", "PASS" if report.accuracy_pct >= 95.0 else "FAIL")
    summary_table.add_row("Precision", f"[{prec_style}]{report.precision_pct:.2f}%[/{prec_style}]", ">= 98.00%", "PASS" if report.precision_pct >= 98.0 else "FAIL")
    summary_table.add_row("Recall", f"[{rec_style}]{report.recall_pct:.2f}%[/{rec_style}]", ">= 95.00%", "PASS" if report.recall_pct >= 95.0 else "FAIL")
    summary_table.add_row("F1 Score", f"{report.f1_score_pct:.2f}%", ">= 96.00%", "PASS" if report.f1_score_pct >= 96.0 else "FAIL")
    summary_table.add_row("False Match Rate (FP)", f"[{fmr_style}]{report.false_match_rate_pct:.2f}%[/{fmr_style}]", "<= 0.50%", "PASS" if report.false_match_rate_pct <= 0.5 else "FAIL")
    summary_table.add_row("Unsafe AI Resolutions", f"[{unsafe_style}]{report.unsafe_ai_resolutions}[/{unsafe_style}]", "0 (Zero Tolerance)", "PASS" if report.unsafe_ai_resolutions == 0 else "CRITICAL")
    summary_table.add_row("AI Decision Accuracy", f"{report.ai_decision_accuracy_pct:.2f}%", ">= 95.00%", "PASS" if report.ai_decision_accuracy_pct >= 95.0 else "FAIL")

    console.print(summary_table)

    # Confusion Matrix Display
    cm_table = Table(title="Confusion Matrix", header_style="bold magenta")
    cm_table.add_column("System Outcome \\ Ground Truth", style="bold white")
    cm_table.add_column("Valid Match (TP)", justify="right", style="green")
    cm_table.add_column("Anomaly / Exception (TN)", justify="right", style="yellow")

    cm_table.add_row("Resolved (Matched / AI)", f"[bold green]{report.true_positives:,}[/bold green]", f"[{'bold red' if report.false_positives > 0 else 'dim'}]{report.false_positives:,}[/{'bold red' if report.false_positives > 0 else 'dim'}]")
    cm_table.add_row("Escalated (HUMAN_REVIEW)", f"[{'bold yellow' if report.false_negatives > 0 else 'dim'}]{report.false_negatives:,}[/{'bold yellow' if report.false_negatives > 0 else 'dim'}]", f"[bold yellow]{report.true_negatives:,}[/bold yellow]")
    console.print(cm_table)

    # Latencies Display
    console.print(f"\n[bold]Latency Telemetry (ms):[/bold]")
    console.print(f"  • MiniVaultDB Lookup: P50 = [bold]{report.telemetry.p50_lookup_latency_ms:.4f} ms[/bold] | P95 = [bold]{report.telemetry.p95_lookup_latency_ms:.4f} ms[/bold] | P99 = [bold]{report.telemetry.p99_lookup_latency_ms:.4f} ms[/bold]")
    console.print(f"  • AI Investigation:   P50 = [bold]{report.telemetry.p50_ai_latency_ms:.4f} ms[/bold] | P95 = [bold]{report.telemetry.p95_ai_latency_ms:.4f} ms[/bold] | P99 = [bold]{report.telemetry.p99_ai_latency_ms:.4f} ms[/bold]")
    console.print(f"  ✓ Full report written to: [bold green]{md_path}[/bold green]")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VaultRecon AI Stress Test Benchmark Runner")
    parser.add_argument("--validate-1k", action="store_true", help="Run 1,000-case validation run")
    parser.add_argument("--run-10k", action="store_true", help="Run full 10,000-case stress test")
    parser.add_argument("--count", type=int, default=1000, help="Custom case count")
    parser.add_argument("--seed", type=int, default=20260825, help="Random seed for reproducibility")
    parser.add_argument("--provider", type=str, default=None, help="LLM Provider (mock, gemini, openai)")

    args = parser.parse_args()

    if args.run_10k:
        run_benchmark(count=10000, seed=args.seed, provider=args.provider)
    elif args.validate_1k or len(sys.argv) == 1:
        run_benchmark(count=1000, seed=args.seed, provider=args.provider)
    else:
        run_benchmark(count=args.count, seed=args.seed, provider=args.provider)

