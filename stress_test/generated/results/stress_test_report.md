# VaultRecon AI — Stress Test & Adversarial Evaluation Report

**Total Cases Evaluated:** 1,000 cases  
**Generated Pipeline Records:** 2,890 records  

## 1. Executive Summary

| Metric | Measured Value | Benchmark Threshold | Status |
| :--- | :---: | :---: | :---: |
| **Overall Accuracy** | **95.00%** | $\ge 95.00\%$ | PASS |
| **Precision** | **100.00%** | $\ge 98.00\%$ | PASS |
| **Recall** | **91.67%** | $\ge 95.00\%$ | FAIL |
| **F1 Score** | **95.65%** | $\ge 96.00\%$ | FAIL |
| **False Match Rate (FP)** | **0.00%** | $\le 0.50\%$ | PASS |
| **Unsafe AI Resolutions** | **0** | **0** | PASS |
| **AI Decision Accuracy** | **82.22%** | $\ge 95.00\%$ | FAIL |

## 2. Confusion Matrix

| Classification | Ground Truth: Valid Match (TP) | Ground Truth: Anomaly / Exception (TN) |
| :--- | :---: | :---: |
| **System Resolved (Matched / AI)** | **TP: 550** | **FP: 0** |
| **System Escalated (HUMAN_REVIEW)** | **FN: 50** | **TN: 400** |

## 3. Performance & Latency Telemetry

| Stage | Duration | Throughput |
| :--- | :---: | :---: |
| **MiniVaultDB Ingestion** | 0.221 s | 13,089.1 records/sec |
| **Deterministic Reconciliation** | 0.064 s | 15,028.5 cases/sec |
| **AI Controller Investigation** | 0.606 s | 792.0 exceptions/sec |
| **Total Pipeline (End-to-End)** | 0.893 s | 1,074.9 cases/sec |

### Latency Distributions (ms)

- **MiniVaultDB Record Lookup:** P50: `0.0028 ms` | P95: `0.0031 ms` | P99: `0.0033 ms`
- **AI Investigation:** P50: `1.3910 ms` | P95: `2.0514 ms` | P99: `2.8506 ms`

## 4. Per-Scenario Forensic Breakdown

| Scenario Type | Total | Correct | Accuracy | TP | TN | FP | FN |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `EXACT_MATCH` | 350 | 350 | 100.00% | 350 | 0 | 0 | 0 |
| `TIMING_MATCH` | 100 | 100 | 100.00% | 100 | 0 | 0 | 0 |
| `TOLERANCE_MATCH` | 40 | 40 | 100.00% | 40 | 0 | 0 | 0 |
| `FUZZY_DESCRIPTION_MATCH` | 30 | 30 | 100.00% | 30 | 0 | 0 | 0 |
| `PARTIAL_PAYMENT` | 30 | 0 | 0.00% | 0 | 0 | 0 | 30 |
| `FEE_MISMATCH_RESOLVABLE` | 30 | 30 | 100.00% | 30 | 0 | 0 | 0 |
| `BUNDLED_PAYMENT_RESOLVABLE` | 20 | 0 | 0.00% | 0 | 0 | 0 | 20 |
| `FEE_MISMATCH_UNRESOLVABLE` | 50 | 50 | 100.00% | 0 | 50 | 0 | 0 |
| `AMOUNT_MISMATCH` | 50 | 50 | 100.00% | 0 | 50 | 0 | 0 |
| `MISSING_PROCESSOR` | 40 | 40 | 100.00% | 0 | 40 | 0 | 0 |
| `MISSING_INTERNAL` | 40 | 40 | 100.00% | 0 | 40 | 0 | 0 |
| `DUPLICATE_PROCESSOR` | 30 | 30 | 100.00% | 0 | 30 | 0 | 0 |
| `DUPLICATE_INTERNAL` | 30 | 30 | 100.00% | 0 | 30 | 0 | 0 |
| `PARTIAL_REFUND` | 30 | 30 | 100.00% | 0 | 30 | 0 | 0 |
| `CURRENCY_MISMATCH` | 20 | 20 | 100.00% | 0 | 20 | 0 | 0 |
| `LATE_SETTLEMENT` | 20 | 20 | 100.00% | 0 | 20 | 0 | 0 |
| `MISSING_BANK_DEPOSIT` | 20 | 20 | 100.00% | 0 | 20 | 0 | 0 |
| `UNKNOWN_FEE_POLICY` | 10 | 10 | 100.00% | 0 | 10 | 0 | 0 |
| `BUNDLED_PAYMENT_AMBIGUOUS` | 10 | 10 | 100.00% | 0 | 10 | 0 | 0 |
| `ADVERSARIAL_PROMPT_INJECTION` | 20 | 20 | 100.00% | 0 | 20 | 0 | 0 |
| `ADVERSARIAL_HALLUCINATED_ID` | 20 | 20 | 100.00% | 0 | 20 | 0 | 0 |
| `ADVERSARIAL_CONTRADICTION` | 10 | 10 | 100.00% | 0 | 10 | 0 | 0 |