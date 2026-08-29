"""
End-to-End Benchmark Runner for VaultRecon AI.
Executes benchmarks across multiple batch sizes (50, 100, 500, 1000+),
measuring MiniVaultDB latency, ingestion throughput, deterministic match rate,
and AI resolution accuracy against ground truth.
"""

import time
import shutil
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from recon.storage import MiniVaultDBClient
from ingestion.generators import SyntheticDataGenerator
from ingestion.loader import IngestionLoader
from recon.matcher import ReconciliationEngine
from ai.agent import AIController
from ai.llm import BaseLLMProvider, MockLLMProvider, get_llm_provider
from evaluation.metrics import MetricsEvaluator, ReconciliationMetrics


class BenchmarkRunner:
    def __init__(
        self,
        db_dir: str = "./testdb_benchmarks",
        llm_provider: Optional[BaseLLMProvider] = None,
        console: Optional[Console] = None,
    ):
        self.db_dir = db_dir
        self.llm_provider = llm_provider or get_llm_provider()
        self.console = console or Console()

    def run_benchmark(self, record_count: int = 100, seed: int = 42) -> ReconciliationMetrics:
        """
        Execute end-to-end pipeline on `record_count` financial cases.
        """
        shutil.rmtree(self.db_dir, ignore_errors=True)

        with MiniVaultDBClient(db_dir=self.db_dir, memtable_bytes=32 * 1024 * 1024) as db:
            # 1. Synthetic Data Generation
            generator = SyntheticDataGenerator(seed=seed)
            dataset = generator.generate(count=record_count)

            # 2. Ingestion into MiniVaultDB
            loader = IngestionLoader(db)
            ingest_report = loader.load_dataset(dataset)

            # 3. Deterministic Reconciliation & Measure Latency per case
            engine = ReconciliationEngine(db)
            latencies_ms: List[float] = []

            for pay in dataset.payments:
                t0 = time.perf_counter()
                engine.reconcile_payment(pay)
                t1 = time.perf_counter()
                latencies_ms.append((t1 - t0) * 1000.0)

            # Full batch reconciliation report
            matcher_report = engine.reconcile_all(dataset.payments)

            # 4. AI Controller Investigation on Generated Exceptions
            ai_controller = AIController(db, llm_provider=self.llm_provider)
            investigated_exceptions = []

            for exc in matcher_report.exceptions:
                ai_controller.investigate(exc)
                investigated_exceptions.append(exc)

            # 5. Evaluate Metrics against Ground Truth
            metrics = MetricsEvaluator.evaluate(
                ground_truth=dataset.ground_truth,
                matcher_report=matcher_report,
                resolved_exceptions=investigated_exceptions,
                ingestion_throughput=ingest_report.throughput_records_per_sec,
                latencies_ms=latencies_ms,
            )

        shutil.rmtree(self.db_dir, ignore_errors=True)
        return metrics

    def run_suite(self, sizes: List[int] = [50, 100, 500, 1000]) -> Dict[int, ReconciliationMetrics]:
        """
        Run benchmarks across all target dataset sizes and print summary comparison table.
        """
        results: Dict[int, ReconciliationMetrics] = {}

        self.console.print(Panel("[bold cyan]VaultRecon AI — End-to-End System Evaluation Benchmark[/bold cyan]", expand=False))

        table = Table(title="VaultRecon AI System Benchmark Results", header_style="bold magenta")
        table.add_column("Records", justify="right", style="cyan")
        table.add_column("Deterministic Match", justify="right", style="green")
        table.add_column("Exceptions", justify="right", style="yellow")
        table.add_column("AI Resolved", justify="right", style="blue")
        table.add_column("Human Review", justify="right", style="red")
        table.add_column("Accuracy", justify="right", style="bold green")
        table.add_column("Total Recon %", justify="right", style="bold green")
        table.add_column("Ingest (rec/s)", justify="right")
        table.add_column("Recon (rec/s)", justify="right")
        table.add_column("P50 (ms)", justify="right")
        table.add_column("P95 (ms)", justify="right")

        for size in sizes:
            self.console.print(f"[dim]Running benchmark for {size} records...[/dim]")
            m = self.run_benchmark(record_count=size)
            results[size] = m

            table.add_row(
                str(m.total_records),
                f"{m.deterministic_matched} ({m.deterministic_match_rate*100:.1f}%)",
                str(m.exceptions_generated),
                str(m.ai_resolved),
                str(m.human_review),
                f"{m.ground_truth_accuracy*100:.1f}%",
                f"{m.total_reconciliation_rate*100:.1f}%",
                f"{m.ingestion_throughput:,.0f}",
                f"{m.recon_throughput:,.0f}",
                f"{m.p50_latency_ms:.4f}",
                f"{m.p95_latency_ms:.4f}",
            )

        self.console.print(table)
        return results

