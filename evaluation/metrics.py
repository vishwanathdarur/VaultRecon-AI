"""
Evaluation Metrics Tracker for VaultRecon AI.
Computes ground truth accuracy, precision, recall, false match rates,
and throughput/latency metrics.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import numpy as np

from ingestion.generators import GroundTruthCase
from recon.matcher import MatcherReport
from recon.exceptions import FinancialException


@dataclass
class ReconciliationMetrics:
    total_records: int
    deterministic_matched: int
    exceptions_generated: int
    ai_investigated: int
    ai_resolved: int
    human_review: int
    deterministic_match_rate: float
    total_reconciliation_rate: float
    ground_truth_accuracy: float
    precision: float
    recall: float
    f1_score: float
    false_match_count: int
    false_resolution_count: int
    ingestion_throughput: float
    recon_throughput: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float


class MetricsEvaluator:
    @staticmethod
    def evaluate(
        ground_truth: List[GroundTruthCase],
        matcher_report: MatcherReport,
        resolved_exceptions: List[FinancialException],
        ingestion_throughput: float,
        latencies_ms: List[float],
    ) -> ReconciliationMetrics:
        """
        Compare system results against ground truth labels.
        """
        gt_map = {gt.case_id: gt for gt in ground_truth}

        # Build index of results by transaction ID
        total_eval = matcher_report.total_evaluated
        det_matched = matcher_report.matched_count
        exc_count = matcher_report.exception_count

        ai_resolved = sum(1 for e in resolved_exceptions if e.status == "AI_RESOLVED")
        human_review = sum(1 for e in resolved_exceptions if e.status == "HUMAN_REVIEW")

        tp = 0  # Truly matched correctly (or resolved correctly)
        fp = 0  # Marked matched/resolved when expected was HUMAN_REVIEW / fraud
        fn = 0  # Marked HUMAN_REVIEW when it should have matched/resolved
        tn = 0  # Correctly escalated to HUMAN_REVIEW

        false_matches = 0
        false_resolutions = 0

        # Evaluate deterministic matches against ground truth
        matched_payment_ids = (
            {m.internal_payment_id for m in matcher_report.matches if m.internal_payment_id}
            | {m.work_key for m in matcher_report.matches}
            | {m.processor_transaction_id for m in matcher_report.matches if m.processor_transaction_id}
            | {m.bank_entry_id for m in matcher_report.matches if m.bank_entry_id}
        )

        for gt in ground_truth:
            expected = gt.expected_decision  # MATCHED, AI_RESOLVED, HUMAN_REVIEW
            pids = gt.primary_record_ids

            is_matched = any(pid in matched_payment_ids for pid in pids)

            if is_matched:
                actual = "MATCHED"
            else:
                # Look up exception for this case
                matching_exc = next(
                    (e for e in resolved_exceptions if any(pid == e.primary_record_id or pid in e.related_record_ids for pid in pids)),
                    None,
                )
                if matching_exc:
                    actual = matching_exc.status  # AI_RESOLVED or HUMAN_REVIEW
                else:
                    actual = "UNKNOWN"

            if expected in ("MATCHED", "AI_RESOLVED"):
                if actual in ("MATCHED", "AI_RESOLVED"):
                    tp += 1
                else:
                    fn += 1
            elif expected == "HUMAN_REVIEW":
                if actual == "HUMAN_REVIEW":
                    tn += 1
                elif actual in ("MATCHED", "AI_RESOLVED"):
                    fp += 1
                    if actual == "MATCHED":
                        false_matches += 1
                    else:
                        false_resolutions += 1

        precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 1.0
        accuracy = (tp + tn) / len(ground_truth) if ground_truth else 1.0

        p50 = float(np.percentile(latencies_ms, 50)) if latencies_ms else 0.0
        p95 = float(np.percentile(latencies_ms, 95)) if latencies_ms else 0.0
        p99 = float(np.percentile(latencies_ms, 99)) if latencies_ms else 0.0

        det_rate = round(det_matched / total_eval, 4) if total_eval else 0.0
        total_recon_rate = round((det_matched + ai_resolved) / total_eval, 4) if total_eval else 0.0

        return ReconciliationMetrics(
            total_records=total_eval,
            deterministic_matched=det_matched,
            exceptions_generated=exc_count,
            ai_investigated=len(resolved_exceptions),
            ai_resolved=ai_resolved,
            human_review=human_review,
            deterministic_match_rate=det_rate,
            total_reconciliation_rate=total_recon_rate,
            ground_truth_accuracy=round(accuracy, 4),
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1_score=round(f1, 4),
            false_match_count=false_matches,
            false_resolution_count=false_resolutions,
            ingestion_throughput=ingestion_throughput,
            recon_throughput=matcher_report.throughput_records_per_sec,
            p50_latency_ms=round(p50, 4),
            p95_latency_ms=round(p95, 4),
            p99_latency_ms=round(p99, 4),
        )

