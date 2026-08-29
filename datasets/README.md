# VaultRecon AI — Default Demonstration Dataset

This directory contains the **official self-contained default dataset** for demonstrating the complete VaultRecon AI reconciliation pipeline.

---

## 1. Overview

The default dataset is a **realistic, synthetic, and fully reproducible** multi-source financial dataset (`seed=42`). It generates records on the fly across standard corporate accounting structures without requiring manual downloads or external dependencies.

> [!NOTE]
> This dataset is synthetic and designed to rigorously demonstrate both clean matching paths and real-world exception handling.

---

## 2. Injected Reconciliation Scenarios

The dataset covers all core reconciliation topologies supported by VaultRecon AI:

| Scenario | Typical Share | Expected System Behavior | Output Outcome |
| :--- | :---: | :--- | :--- |
| **Exact 1:1 Matches** | ~70% | Same day, exact cents, standard 2.0% card fee or 0% direct debit | `MATCHED` (`EXACT`) |
| **Timing Differences** | ~8% | Exact amount cleared 1 to 3 days late (clearing lag) | `MATCHED` (`TIMING`) |
| **Penny Tolerances** | ~5% | Amount variance $\le \$0.03$ (penny tax/rounding) | `MATCHED` (`TOLERANCE`) |
| **International Surcharges** | ~4% | Contractual 3.5% international card fee rule applied | `AI_RESOLVED` |
| **Unresolvable Fee Markups** | ~4% | Arbitrary 15% gateway fee exceeding policy | `HUMAN_REVIEW` |
| **Gross Amount Mismatch** | ~3% | Invoice amount differs from payment by $\$75.00$ | `HUMAN_REVIEW` |
| **Missing Gateway Record** | ~3% | Internal payment logged, but gateway never captured | `HUMAN_REVIEW` |
| **Partial Refund Netting** | ~3% | Unrecorded $40\%$ refund reducing settled amount | `HUMAN_REVIEW` |
| **Settlement Payout Batches** | 1 per 10 txns | Aggregated net batch matched to bank deposit with SLA | `MATCHED` (`BATCH`) |

---

## 3. How to Run

To run the default dataset through the complete pipeline (Ingestion $\rightarrow$ MiniVaultDB $\rightarrow$ Reconciliation $\rightarrow$ AI Controller):

```bash
# Default (100 cases)
python3 datasets/run.py

# Custom record count
python3 datasets/run.py --records 500 --provider mock
```

Or simply run the root convenience CLI:

```bash
python3 run_reconciliation.py
```

---

## 4. Dataset Files & Architecture

* **[`generator.py`](generator.py)**: Implements `DefaultDatasetGenerator`, creating `NormalizedDataset` objects.
* **[`run.py`](run.py)**: Orchestrates database ingestion, multi-pass deterministic matching, AI exception forensic investigation, and performance metric reporting.
* **[`data/`](data/)**: Canonical CSV dataset (7 financial sources: payments, processor_transactions, bank_transactions, invoices, settlements, refunds, fee_policies).

