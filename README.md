# VaultRecon AI

**High-Throughput Financial Reconciliation System with C++ LSM Storage & Guardrailed AI Forensic Controller**

VaultRecon AI bridges the gap between high-speed database engineering and autonomous financial operations. It ingests multi-source financial feeds into **MiniVaultDB** (a custom C++ LSM key-value engine), executes multi-pass deterministic reconciliation at **~19,700 cases/sec**, and autonomously investigates complex financial discrepancies using a **guardrailed AI forensic controller** with 100% precision and zero false matches.

---

## ⚡ Quick Start

### 1. Installation & Build

```bash
# Clone repository
git clone https://github.com/vishwanathdarur/VaultRecon-AI.git
cd VaultRecon-AI

# Install Python dependencies
pip install -r requirements.txt

# Build MiniVaultDB C++ storage engine shared library
make -C MiniVaultDB
```

### 2. Run the Default Demonstration Pipeline

```bash
PYTHONPATH=. python3 run_reconciliation.py
```

### What happens when you run this command:
1. **Generates Default Dataset**: Creates 100 multi-source financial lifecycle records covering exact matches, timing lags, penny tolerances, fee discrepancies, refunds, and batch payouts.
2. **Ingests into MiniVaultDB**: Persists raw records and secondary index pointers into C++ LSM storage (WAL + MemTable).
3. **Deterministic Reconciliation**: Executes multi-pass staged matching (`EXACT` $\rightarrow$ `TIMING` $\rightarrow$ `TOLERANCE` $\rightarrow$ `FEE POLICY`).
4. **AI Forensic Investigation**: Routes exceptions to the AI Controller, which inspects database evidence and applies strict guardrails.
5. **Prints Summary Report**: Displays throughput, latency, matched counts, AI resolutions, and human review escalations.

---

## 📊 What the Default Dataset Contains

The default dataset in [`datasets/default/`](file:///home/vishwa/Project/VaultRecon-AI/datasets/default/) is a **fully reproducible, synthetic financial dataset** (`seed=42`) generated locally.

It contains real-world financial conditions supported by VaultRecon AI:
* **Exact 1:1 Matches**: Same day, exact cents, standard card/direct debit fee rules.
* **Timing Differences**: Transactions clearing with a 1 to 3 day settlement delay.
* **Penny Tolerances**: Minor VAT/rounding variances ($\le \$0.03$).
* **Resolvable International Surcharges**: Contractual 3.5% international card fees verified by AI.
* **Unresolvable Fee Markups**: Arbitrary 15% gateway markups safely escalated to `HUMAN_REVIEW`.
* **Gross Amount Mismatches**: Invoice vs. payment discrepancies flagged for review.
* **Missing Gateway Captures**: Internal payments with no external processor settlement.
* **Partial Refund Netting**: Transactions affected by unrecorded customer refunds.
* **Settlement Payout Batches**: Aggregated processor net payouts reconciled against bank deposits within SLA.

---

## 🏗️ System Architecture

```
 User Data / CSV / External Feeds
               │
               ▼
   [ Source Normalization Layer ]
   (ingestion/adapters/ & schemas.py)
               │
               ▼ (NormalizedDataset)
   [ MiniVaultDB Storage Engine ]
   (C++ LSM: WAL + MemTable + SSTables)
               │
               ▼ (Point Lookups & Bulk Secondary Indexes)
 [ Deterministic Reconciliation Engine ]
       (recon/matcher.py & rules.py)
               │
       ┌───────┴───────┐
       ▼               ▼
  [ MATCHED ]    [ FinancialException ]
  (100% Prec.)         │
                       ▼
          [ AI Investigation Controller ]
              (ai/agent.py & tools.py)
                       │
                       ▼
          [ Guardrails & Fact Validator ]
              (ai/guardrails.py)
                       │
               ┌───────┴───────┐
               ▼               ▼
        [ AI_RESOLVED ]  [ HUMAN_REVIEW ]
      (Verified Evidence) (Zero False Matches)
```

For complete architectural details, see [docs/ARCHITECTURE.md](file:///home/vishwa/Project/VaultRecon-AI/docs/ARCHITECTURE.md).

---

## 📁 Uploading Your Own Data

To reconcile your own CSV files:
1. Define a simple header mapping dictionary.
2. Use [`GenericCSVAdapter`](file:///home/vishwa/Project/VaultRecon-AI/ingestion/adapters/generic_csv.py) to normalize into standard record schemas.
3. Run the reconciliation engine.

👉 **Complete Step-by-Step Guide:** [docs/UPLOADING_DATA.md](file:///home/vishwa/Project/VaultRecon-AI/docs/UPLOADING_DATA.md)  
👉 **Canonical Data Model Specs:** [docs/DATASET_FORMAT.md](file:///home/vishwa/Project/VaultRecon-AI/docs/DATASET_FORMAT.md)

> [!NOTE]
> VaultRecon AI requires explicit column mappings and does not perform automatic schema guessing for custom raw CSVs.

---

## 🔬 Additional External Validation Datasets

VaultRecon AI was validated against 4 independent external financial datasets in [`datasets/external/`](file:///home/vishwa/Project/VaultRecon-AI/datasets/external/):

```bash
# 1. ReconRiver Multi-Source Benchmark (1,244 mixed cases)
PYTHONPATH=. python3 datasets/external/reconriver/run.py --scenario all

# 2. R3n0va Accounting ERP Dataset (Invoices, Payments, Bank Statements)
PYTHONPATH=. python3 datasets/external/r3n0va/run.py

# 3. Bank-to-General Ledger Reconciliation (Cheques, PADs, EFTs)
PYTHONPATH=. python3 datasets/external/bank_gl/run.py

# 4. Invoice Payment Matcher (Invoice-to-Deposit & Bundled Payments)
PYTHONPATH=. python3 datasets/external/invoice_matcher/run.py

# 5. Blind Financial Benchmark
PYTHONPATH=. python3 datasets/external/blind_test/run.py
```

---

## 🚀 Performance Benchmarks

Measured on standard commodity hardware across 10,000 evaluated cases (28,900 ingested records):

| Pipeline Stage | Measured Performance | Precision / Safety |
| :--- | :--- | :--- |
| **MiniVaultDB Ingestion** | **21,850 records/sec** | Zero data corruption |
| **MiniVaultDB Point Lookup (P50)** | **0.0020 ms** ($2.0\text{ }\mu\text{s}$) | C-ABI direct memory access |
| **MiniVaultDB Point Lookup (P95)** | **0.0023 ms** ($2.3\text{ }\mu\text{s}$) | Bloom filter skip |
| **Deterministic Reconciliation** | **19,706 cases/sec** ($0.487\text{ s}$ for 10k) | **0 False Matches (100% Precision)** |
| **AI Investigation Controller** | **0.36 ms / exception** (Mock) | **0 Unsafe AI Resolutions** |
| **Overall 10K Accuracy** | **98.00% Accuracy (F1: 98.31%)** | Recall: 96.67% |

To run the multi-scale performance benchmark (50, 100, 500, 1,000 orders):
```bash
PYTHONPATH=. python3 evaluate.py
```

---

## 🧪 Testing & Verification

Run the full regression test suite (45 unit tests):

```bash
PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_*.py'
```

Run the AI safety evaluation suite (12 adversarial scenarios):

```bash
PYTHONPATH=. python3 investigate.py --eval-suite
```

---

## 🛡️ 10,000-Case Adversarial Stress Testing

Run the independent stress testing suite covering 22 adversarial conditions (prompt injections, hallucinated IDs, contradictory records):

```bash
# 1,000-case quick validation
PYTHONPATH=. python3 stress_test/benchmark.py --validate-1k

# Full 10,000-case stress test
PYTHONPATH=. python3 stress_test/benchmark.py --run-10k
```

---

## ⚠️ Known Limitations

1. **Ad-Hoc Bundled Payments Without Grouping Keys**: When a single bank deposit combines multiple invoices without a shared customer reference or remittance advice, combinatorial matching requires external remittance metadata.
2. **Schema Inference**: Automatic zero-configuration CSV column inference is not implemented; column mappings must be explicitly defined via `GenericCSVAdapter`.