"""
Production Reconciliation Pipeline Runner for VaultRecon AI Stress Testing.
Executes MiniVaultDB ingestion, deterministic reconciliation, and AI investigation controller,
collecting fine-grained performance telemetry and latency distributions.
"""

import time
import shutil
import os
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import numpy as np

from recon.storage import MiniVaultDBClient
from recon.rules import ReconciliationRules, FeePolicyRegistry
from recon.matcher import ReconciliationEngine, ReconciliationMatch, MatcherReport
from recon.exceptions import FinancialException
from ai.agent import AIController, AIDecisionResult
from ai.llm import MockLLMProvider, get_llm_provider
from ingestion.adapters.base import NormalizedDataset
from ingestion.loader import IngestionLoader


class PerformanceTelemetry(BaseModel):
    ingestion_duration_sec: float = 0.0
    ingestion_throughput_rps: float = 0.0
    deterministic_duration_sec: float = 0.0
    deterministic_throughput_cps: float = 0.0
    ai_duration_sec: float = 0.0
    ai_throughput_eps: float = 0.0
    total_pipeline_duration_sec: float = 0.0
    total_pipeline_throughput_cps: float = 0.0
    
    # Latencies in milliseconds
    p50_lookup_latency_ms: float = 0.0
    p95_lookup_latency_ms: float = 0.0
    p99_lookup_latency_ms: float = 0.0
    
    p50_ai_latency_ms: float = 0.0
    p95_ai_latency_ms: float = 0.0
    p99_ai_latency_ms: float = 0.0


class StressTestRunResult(BaseModel):
    total_input_records: int
    total_evaluated_cases: int
    matched_count: int
    exception_count: int
    ai_resolved_count: int
    human_review_count: int
    
    matches: List[Dict[str, Any]] = Field(default_factory=list)
    exceptions: List[Dict[str, Any]] = Field(default_factory=list)
    ai_results: List[Dict[str, Any]] = Field(default_factory=list)
    telemetry: PerformanceTelemetry


class StressTestRunner:
    def __init__(self, db_dir: str = "./testdb_stress_run", provider: Optional[str] = None):
        self.db_dir = db_dir
        self.provider = provider

    def run(self, dataset: NormalizedDataset) -> StressTestRunResult:
        """
        Execute full production pipeline against provided NormalizedDataset.
        """
        shutil.rmtree(self.db_dir, ignore_errors=True)
        t_pipe_start = time.perf_counter()

        lookup_latencies_ms: List[float] = []
        ai_latencies_ms: List[float] = []

        with MiniVaultDBClient(db_dir=self.db_dir, memtable_bytes=64 * 1024 * 1024) as db:
            # 1. MiniVaultDB Ingestion
            loader = IngestionLoader(db)
            t_ingest_start = time.perf_counter()
            ingest_report = loader.load_dataset(dataset)
            t_ingest_end = time.perf_counter()
            ingest_dur = max(t_ingest_end - t_ingest_start, 1e-6)

            # 2. Deterministic Multi-Pass Reconciliation
            rules = ReconciliationRules(
                topology="GATEWAY_SETTLEMENT",
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
            report = engine.reconcile_all(dataset.payments)
            t_recon_end = time.perf_counter()
            recon_dur = max(t_recon_end - t_recon_start, 1e-6)

            # Measure fine-grained lookup latencies
            sample_payments = dataset.payments[:min(500, len(dataset.payments))]
            for p in sample_payments:
                t0 = time.perf_counter()
                db.get_record("PROCESSOR", p.transaction_id)
                t1 = time.perf_counter()
                lookup_latencies_ms.append((t1 - t0) * 1000.0)

            # 3. Autonomous AI Controller Investigation on all Exceptions
            controller = AIController(db, llm_provider=get_llm_provider(self.provider), fee_registry=rules.fee_registry)

            ai_results: List[AIDecisionResult] = []
            t_ai_start = time.perf_counter()
            for exc in report.exceptions:
                t0 = time.perf_counter()
                res = controller.investigate(exc)
                t1 = time.perf_counter()
                ai_latencies_ms.append((t1 - t0) * 1000.0)
                ai_results.append(res)
            t_ai_end = time.perf_counter()
            ai_dur = max(t_ai_end - t_ai_start, 1e-6)

        t_pipe_end = time.perf_counter()
        total_pipe_dur = max(t_pipe_end - t_pipe_start, 1e-6)

        shutil.rmtree(self.db_dir, ignore_errors=True)

        # Telemetry calculations
        p50_l = float(np.percentile(lookup_latencies_ms, 50)) if lookup_latencies_ms else 0.0
        p95_l = float(np.percentile(lookup_latencies_ms, 95)) if lookup_latencies_ms else 0.0
        p99_l = float(np.percentile(lookup_latencies_ms, 99)) if lookup_latencies_ms else 0.0

        p50_ai = float(np.percentile(ai_latencies_ms, 50)) if ai_latencies_ms else 0.0
        p95_ai = float(np.percentile(ai_latencies_ms, 95)) if ai_latencies_ms else 0.0
        p99_ai = float(np.percentile(ai_latencies_ms, 99)) if ai_latencies_ms else 0.0

        telemetry = PerformanceTelemetry(
            ingestion_duration_sec=ingest_dur,
            ingestion_throughput_rps=dataset.total_records / ingest_dur,
            deterministic_duration_sec=recon_dur,
            deterministic_throughput_cps=report.total_evaluated / recon_dur,
            ai_duration_sec=ai_dur,
            ai_throughput_eps=len(report.exceptions) / ai_dur if report.exceptions else 0.0,
            total_pipeline_duration_sec=total_pipe_dur,
            total_pipeline_throughput_cps=report.total_evaluated / total_pipe_dur,
            p50_lookup_latency_ms=p50_l,
            p95_lookup_latency_ms=p95_l,
            p99_lookup_latency_ms=p99_l,
            p50_ai_latency_ms=p50_ai,
            p95_ai_latency_ms=p95_ai,
            p99_ai_latency_ms=p99_ai,
        )

        ai_resolved = sum(1 for e in report.exceptions if e.status == "AI_RESOLVED")
        human_review = sum(1 for e in report.exceptions if e.status == "HUMAN_REVIEW")

        from dataclasses import asdict

        return StressTestRunResult(
            total_input_records=dataset.total_records,
            total_evaluated_cases=report.total_evaluated,
            matched_count=report.matched_count,
            exception_count=report.exception_count,
            ai_resolved_count=ai_resolved,
            human_review_count=human_review,
            matches=[asdict(m) for m in report.matches],
            exceptions=[e.model_dump() for e in report.exceptions],
            ai_results=[r.model_dump() for r in ai_results],
            telemetry=telemetry,
        )
