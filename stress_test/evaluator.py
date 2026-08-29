"""
Independent Evaluator and Benchmark Reporter for VaultRecon AI Stress Testing.
Compares actual execution results against hidden ground truth without leaking data to the engine.
"""

import os
import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from stress_test.ground_truth import GroundTruthDataset, GroundTruthRecord
from stress_test.runner import StressTestRunResult, PerformanceTelemetry
from stress_test.scenarios import ScenarioType


class ScenarioMetric(BaseModel):
    scenario_type: str
    total_cases: int
    correct_cases: int
    accuracy_pct: float
    true_positives: int
    true_negatives: int
    false_positives: int
    false_negatives: int


class EvaluationReport(BaseModel):
    total_cases: int
    true_positives: int
    true_negatives: int
    false_positives: int
    false_negatives: int
    
    accuracy_pct: float
    precision_pct: float
    recall_pct: float
    f1_score_pct: float
    false_match_rate_pct: float
    
    # AI Specific Metrics
    total_exceptions_investigated: int
    ai_resolved_count: int
    human_review_count: int
    unsafe_ai_resolutions: int
    ai_decision_accuracy_pct: float
    
    scenario_breakdown: List[ScenarioMetric]
    telemetry: PerformanceTelemetry


class StressTestEvaluator:
    @staticmethod
    def evaluate(run_result: StressTestRunResult, ground_truth: GroundTruthDataset) -> EvaluationReport:
        """
        Evaluate actual run result against hidden ground truth.
        """
        # Map actual outcomes by record ID
        actual_outcomes: Dict[str, Dict[str, Any]] = {}

        # 1. Map Matches
        for m in run_result.matches:
            pay_id = m.get("internal_payment_id") or m.get("work_key")
            proc_id = m.get("processor_transaction_id")
            batch_id = m.get("settlement_batch_id") or m.get("work_key")
            bank_id = m.get("bank_entry_id")

            entry = {
                "outcome": "MATCHED",
                "strategy": m.get("match_strategy"),
                "exception_type": None,
                "ai_decision": None,
            }
            if pay_id:
                actual_outcomes[pay_id] = entry
            if proc_id:
                actual_outcomes[proc_id] = entry
            if batch_id:
                actual_outcomes[batch_id] = entry
            if bank_id:
                actual_outcomes[bank_id] = entry

        # 2. Map Exceptions & AI Decisions
        for exc in run_result.exceptions:
            prim_id = exc.get("primary_record_id")
            rel_ids = exc.get("related_record_ids", [])
            exc_type = exc.get("exception_type")
            status = exc.get("status")  # AI_RESOLVED, HUMAN_REVIEW, OPEN
            
            # Map under primary ID
            entry = {
                "outcome": "EXCEPTION",
                "exception_type": exc_type,
                "ai_decision": status,
            }
            actual_outcomes[prim_id] = entry
            for r in rel_ids:
                if r not in actual_outcomes:
                    actual_outcomes[r] = entry

        # Confusion Matrix Counters
        tp = 0
        tn = 0
        fp = 0
        fn = 0
        unsafe_ai = 0
        ai_correct = 0
        total_ai_evals = 0

        # Scenario breakdown counters
        scenario_stats: Dict[ScenarioType, Dict[str, int]] = {
            st: {"total": 0, "correct": 0, "tp": 0, "tn": 0, "fp": 0, "fn": 0}
            for st in ScenarioType
        }

        for k, gt in ground_truth.cases.items():
            st = gt.scenario_type
            s_dict = scenario_stats[st]
            s_dict["total"] += 1

            actual = actual_outcomes.get(gt.primary_record_id)
            if not actual:
                # Check by order ID
                actual = actual_outcomes.get(gt.order_id, {"outcome": "UNRESOLVED", "exception_type": None, "ai_decision": None})

            actual_outcome = actual.get("outcome")
            actual_ai = actual.get("ai_decision")
            actual_exc = actual.get("exception_type")

            # Determine correctness
            is_resolved_by_system = (actual_outcome == "MATCHED" or actual_ai == "AI_RESOLVED")

            if gt.is_true_positive:
                if is_resolved_by_system:
                    tp += 1
                    s_dict["tp"] += 1
                    s_dict["correct"] += 1
                else:
                    fn += 1
                    s_dict["fn"] += 1
            else:
                # Expected to remain an exception escalated to HUMAN_REVIEW
                if is_resolved_by_system:
                    fp += 1  # FALSE MATCH / UNSAFE RESOLUTION!
                    s_dict["fp"] += 1
                    if actual_ai == "AI_RESOLVED":
                        unsafe_ai += 1
                else:
                    tn += 1
                    s_dict["tn"] += 1
                    s_dict["correct"] += 1

            # AI decision evaluation
            if gt.expected_ai_decision is not None:
                total_ai_evals += 1
                if actual_ai == gt.expected_ai_decision:
                    ai_correct += 1

        total = len(ground_truth.cases)
        accuracy = ((tp + tn) / total) * 100.0 if total > 0 else 0.0
        precision = (tp / (tp + fp)) * 100.0 if (tp + fp) > 0 else 0.0
        recall = (tp / (tp + fn)) * 100.0 if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        fmr = (fp / (tp + fp)) * 100.0 if (tp + fp) > 0 else 0.0
        ai_acc = (ai_correct / total_ai_evals) * 100.0 if total_ai_evals > 0 else 100.0

        scenario_metrics = [
            ScenarioMetric(
                scenario_type=st.value,
                total_cases=v["total"],
                correct_cases=v["correct"],
                accuracy_pct=(v["correct"] / v["total"] * 100.0) if v["total"] > 0 else 0.0,
                true_positives=v["tp"],
                true_negatives=v["tn"],
                false_positives=v["fp"],
                false_negatives=v["fn"],
            )
            for st, v in scenario_stats.items()
            if v["total"] > 0
        ]

        report = EvaluationReport(
            total_cases=total,
            true_positives=tp,
            true_negatives=tn,
            false_positives=fp,
            false_negatives=fn,
            accuracy_pct=accuracy,
            precision_pct=precision,
            recall_pct=recall,
            f1_score_pct=f1,
            false_match_rate_pct=fmr,
            total_exceptions_investigated=run_result.exception_count,
            ai_resolved_count=run_result.ai_resolved_count,
            human_review_count=run_result.human_review_count,
            unsafe_ai_resolutions=unsafe_ai,
            ai_decision_accuracy_pct=ai_acc,
            scenario_breakdown=scenario_metrics,
            telemetry=run_result.telemetry,
        )

        return report

    @staticmethod
    def save_reports(report: EvaluationReport, output_dir: str = "stress_test/generated/results") -> Tuple[str, str]:
        os.makedirs(output_dir, exist_ok=True)
        json_path = os.path.join(output_dir, "stress_test_report.json")
        md_path = os.path.join(output_dir, "stress_test_report.md")

        # Save JSON
        with open(json_path, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2))

        # Save Markdown
        md_content = StressTestEvaluator._build_markdown_report(report)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        return json_path, md_path

    @staticmethod
    def _build_markdown_report(report: EvaluationReport) -> str:
        lines = [
            f"# VaultRecon AI — Stress Test & Adversarial Evaluation Report",
            f"",
            f"**Total Cases Evaluated:** {report.total_cases:,} cases  ",
            f"**Generated Pipeline Records:** {int(report.telemetry.ingestion_throughput_rps * report.telemetry.ingestion_duration_sec):,} records  ",
            f"",
            f"## 1. Executive Summary",
            f"",
            f"| Metric | Measured Value | Benchmark Threshold | Status |",
            f"| :--- | :---: | :---: | :---: |",
            f"| **Overall Accuracy** | **{report.accuracy_pct:.2f}%** | $\\ge 95.00\\%$ | {'PASS' if report.accuracy_pct >= 95.0 else 'FAIL'} |",
            f"| **Precision** | **{report.precision_pct:.2f}%** | $\\ge 98.00\\%$ | {'PASS' if report.precision_pct >= 98.0 else 'FAIL'} |",
            f"| **Recall** | **{report.recall_pct:.2f}%** | $\\ge 95.00\\%$ | {'PASS' if report.recall_pct >= 95.0 else 'FAIL'} |",
            f"| **F1 Score** | **{report.f1_score_pct:.2f}%** | $\\ge 96.00\\%$ | {'PASS' if report.f1_score_pct >= 96.0 else 'FAIL'} |",
            f"| **False Match Rate (FP)** | **{report.false_match_rate_pct:.2f}%** | $\\le 0.50\\%$ | {'PASS' if report.false_match_rate_pct <= 0.5 else 'FAIL'} |",
            f"| **Unsafe AI Resolutions** | **{report.unsafe_ai_resolutions}** | **0** | {'PASS' if report.unsafe_ai_resolutions == 0 else 'CRITICAL HAZARD'} |",
            f"| **AI Decision Accuracy** | **{report.ai_decision_accuracy_pct:.2f}%** | $\\ge 95.00\\%$ | {'PASS' if report.ai_decision_accuracy_pct >= 95.0 else 'FAIL'} |",
            f"",
            f"## 2. Confusion Matrix",
            f"",
            f"| Classification | Ground Truth: Valid Match (TP) | Ground Truth: Anomaly / Exception (TN) |",
            f"| :--- | :---: | :---: |",
            f"| **System Resolved (Matched / AI)** | **TP: {report.true_positives:,}** | **FP: {report.false_positives:,}** |",
            f"| **System Escalated (HUMAN_REVIEW)** | **FN: {report.false_negatives:,}** | **TN: {report.true_negatives:,}** |",
            f"",
            f"## 3. Performance & Latency Telemetry",
            f"",
            f"| Stage | Duration | Throughput |",
            f"| :--- | :---: | :---: |",
            f"| **MiniVaultDB Ingestion** | {report.telemetry.ingestion_duration_sec:.3f} s | {report.telemetry.ingestion_throughput_rps:,.1f} records/sec |",
            f"| **Deterministic Reconciliation** | {report.telemetry.deterministic_duration_sec:.3f} s | {report.telemetry.deterministic_throughput_cps:,.1f} cases/sec |",
            f"| **AI Controller Investigation** | {report.telemetry.ai_duration_sec:.3f} s | {report.telemetry.ai_throughput_eps:,.1f} exceptions/sec |",
            f"| **Total Pipeline (End-to-End)** | {report.telemetry.total_pipeline_duration_sec:.3f} s | {report.telemetry.total_pipeline_throughput_cps:,.1f} cases/sec |",
            f"",
            f"### Latency Distributions (ms)",
            f"",
            f"- **MiniVaultDB Record Lookup:** P50: `{report.telemetry.p50_lookup_latency_ms:.4f} ms` | P95: `{report.telemetry.p95_lookup_latency_ms:.4f} ms` | P99: `{report.telemetry.p99_lookup_latency_ms:.4f} ms`",
            f"- **AI Investigation:** P50: `{report.telemetry.p50_ai_latency_ms:.4f} ms` | P95: `{report.telemetry.p95_ai_latency_ms:.4f} ms` | P99: `{report.telemetry.p99_ai_latency_ms:.4f} ms`",
            f"",
            f"## 4. Per-Scenario Forensic Breakdown",
            f"",
            f"| Scenario Type | Total | Correct | Accuracy | TP | TN | FP | FN |",
            f"| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
        ]

        for s in report.scenario_breakdown:
            lines.append(f"| `{s.scenario_type}` | {s.total_cases:,} | {s.correct_cases:,} | {s.accuracy_pct:.2f}% | {s.true_positives:,} | {s.true_negatives:,} | {s.false_positives:,} | {s.false_negatives:,} |")

        return "\n".join(lines)
