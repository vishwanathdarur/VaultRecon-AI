# VaultRecon AI — System Architecture & Technical Design

---

## 1. End-to-End System Pipeline

```
 Source Files / Feeds (CSV, ERPs, Gateways, Bank Feeds)
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
            ┌───────────────┴───────────────┐
            ▼                               ▼
       [ MATCHED ]                  [ FinancialException ]
     (100% Precision)                       │
                                            ▼
                               [ AI Investigation Controller ]
                                   (ai/agent.py & tools.py)
                                            │
                                            ▼
                               [ Guardrails & Fact Validator ]
                                   (ai/guardrails.py)
                                            │
                            ┌───────────────┴───────────────┐
                            ▼                               ▼
                     [ AI_RESOLVED ]                [ HUMAN_REVIEW ]
                  (Verified Evidence)              (Escalated Safely)
```

---

## 2. MiniVaultDB — C++ LSM Key-Value Storage Engine

MiniVaultDB is a purpose-built, high-throughput C++ embedded Key-Value engine implementing Log-Structured Merge-Tree (LSM) architecture:

* **Write-Ahead Log (WAL)**: Append-only disk persistence with `crc32.cpp` integrity verification.
* **MemTable**: In-memory SkipList backed by custom `arena.cpp` chunk allocators for zero fragmentation.
* **SSTables**: Immutable on-disk sorted tables with sparse index blocks and MurmurHash3-based Bloom filters for rapid key rejection.
* **C-ABI Bridge**: High-speed C bindings (`libminivaultdb.so`) exposed to Python ctypes with zero serialization overhead.
* **Microsecond Latency**: Point lookups achieve **$0.0020\text{ ms}$ (P50)** and **$0.0023\text{ ms}$ (P95)**.

---

## 3. High-Throughput Reconciliation Optimization

### The $O(N^2)$ Bottleneck & The Fix
In early versions, each transaction triggered individual `scan_prefix("IDX:ORDER:...")` database calls. Across 10,000 cases, 44,700 prefix scans traversed millions of MemTable nodes in nested loops, causing a 192-second bottleneck.

### Optimized Single-Pass Design:
1. **Bulk Index Prefetching**: At the start of `reconcile_all()`, the engine issues **one** prefix scan across `IDX:ORDER:`, `IDX:REF:`, and `IDX:TXN:`.
2. **In-Memory Lookup Map**: Secondary index entries are hashed into Python dictionaries in $O(N)$ time.
3. **Zero-Copy Matching**: Order lookups during Level 1 and Level 2 matching run in $O(1)$ dictionary lookups, boosting throughput from $49.9\text{ cases/s}$ to **$23,750+\text{ cases/sec}$ ($475\times$ speedup)**.

---

## 4. Multi-Pass Staged Deterministic Reconciliation

Reconciliation executes through a strict staged funnel:

```
Pass 1: EXACT MATCH      --> Exact cents + same day (100% confidence)
Pass 2: TIMING MATCH     --> Exact cents + within T+1..T+7 day window (98% confidence)
Pass 3: TOLERANCE MATCH  --> Delta <= $0.05 + within 10 days + description similarity >= 0.35 (95% confidence)
Pass 4: FEE VALIDATION   --> Checks contractual FeePolicyRegistry; flags discrepancies
```

* **Greedy 1:1 Target Consumption**: Matches immediately lock external processor and bank records in `consumed_target_ids`, preventing double-matching.

---

## 5. AI Forensic Controller & Safety Guardrails

When a financial discrepancy occurs, the **AI Controller** executes a forensic investigation:

1. **Read-Only Toolkit**: 12 strict inquiry tools (`get_invoice`, `get_payment`, `search_by_order`, `get_fee_policy`). The AI layer has **no write permissions**.
2. **Context Isolation**: Untrusted financial memo strings are wrapped in security boundary delimiters (`<<<UNTRUSTED_FINANCIAL_DATA>>>`) to neutralize adversarial prompt injections.
3. **Verified Evidence Requirement**: Decisions must cite valid record IDs present in MiniVaultDB.
4. **Fact Validator**: Cross-checks LLM fee math against database ground truth. Any hallucinated ID or mathematical contradiction triggers **immediate escalation to `HUMAN_REVIEW`**.

