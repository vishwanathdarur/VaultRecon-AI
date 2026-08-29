# VaultRecon AI — Canonical Dataset Format Specification

This document defines the **Canonical Financial Data Model** used across VaultRecon AI. 

External datasets (ERPs, CSVs, gateways, bank feeds) are normalized into these source-independent models before being stored in **MiniVaultDB** and reconciled.

---

## 1. Core Architectural Principle

```
Raw CSV / ERP / API Feeds
         │
         ▼
[ Source Adapter / Normalizer ]
         │
         ▼ (Standardized Pydantic Models)
[ NormalizedDataset ]
         │
         ▼
[ MiniVaultDB Storage Engine (C++ LSM) ]
         │
         ▼
[ Reconciliation Engine & AI Controller ]
```

Decoupling ingestion from matching ensures the deterministic reconciliation engine remains **100% source-agnostic**.

---

## 2. Canonical Financial Record Types

All records inherit from the base `FinancialRecord` schema defined in [`ingestion/schemas.py`](file:///home/vishwa/Project/VaultRecon-AI/ingestion/schemas.py).

---

### A. `PaymentRecord`
Represents an internal ERP, ledger, or order checkout payment record.

```json
{
  "merchant_id": "CORP_01",
  "transaction_id": "PAY_1001",
  "order_id": "ORD_5001",
  "customer_id": "CUST_99",
  "amount": 250.00,
  "currency": "USD",
  "payment_method": "CREDIT_CARD",
  "status": "COMPLETED",
  "timestamp": 1714500000,
  "metadata": {"Memo": "Subscription payment"}
}
```

* **Primary Key:** `REC:PAYMENT:PAY_1001`
* **Secondary Index:** `IDX:ORDER:ORD_5001:PAYMENT:PAY_1001`

---

### B. `InvoiceRecord`
Represents a sales invoice, billing document, or accounts receivable line item.

```json
{
  "merchant_id": "CORP_01",
  "invoice_id": "INV_3001",
  "order_id": "ORD_5001",
  "customer_id": "CUST_99",
  "amount": 250.00,
  "currency": "USD",
  "status": "ISSUED",
  "timestamp": 1714500000
}
```

* **Primary Key:** `REC:INVOICE:INV_3001`
* **Secondary Index:** `IDX:ORDER:ORD_5001:INVOICE:INV_3001`

---

### C. `ProcessorTransaction`
Represents an external payment gateway capture line (Stripe, Razorpay, Adyen, PayPal).

```json
{
  "merchant_id": "CORP_01",
  "processor_transaction_id": "PROC_4001",
  "order_id": "ORD_5001",
  "processor": "STRIPE",
  "gross_amount": 250.00,
  "fee_amount": 5.00,
  "net_amount": 245.00,
  "currency": "USD",
  "status": "SETTLED",
  "batch_id": "BATCH_01",
  "timestamp": 1714500000
}
```

* **Primary Key:** `REC:PROCESSOR:PROC_4001`
* **Secondary Indexes:**
  * `IDX:ORDER:ORD_5001:PROCESSOR:PROC_4001`
  * `IDX:BATCH:BATCH_01:PROCESSOR:PROC_4001`

---

### D. `SettlementRecord` & `SettlementBatch`
Represents aggregated payout batches issued by processors to the corporate bank account.

```json
{
  "merchant_id": "CORP_01",
  "batch_id": "BATCH_01",
  "processor": "STRIPE",
  "total_gross": 5000.00,
  "total_fees": 100.00,
  "total_net": 4900.00,
  "currency": "USD",
  "transaction_count": 20,
  "transaction_ids": ["PROC_4001", "PROC_4002"],
  "timestamp": 1714586400
}
```

* **Primary Key:** `REC:BATCH:BATCH_01`
* **Secondary Index:** `IDX:REF:BATCH_01:BATCH:BATCH_01`

---

### E. `BankTransactionRecord`
Represents an actual bank statement credit or debit line.

```json
{
  "merchant_id": "CORP_01",
  "bank_transaction_id": "BNK_9001",
  "account_id": "ACC_PRIMARY_CHECKING",
  "reference": "BATCH_01",
  "amount": 4900.00,
  "currency": "USD",
  "direction": "CREDIT",
  "description": "DIRECT DEPOSIT STRIPE PAYOUT BATCH_01",
  "timestamp": 1714593600
}
```

* **Primary Key:** `REC:BANK:BNK_9001`
* **Secondary Index:** `IDX:REF:BATCH_01:BANK:BNK_9001`

---

### F. `RefundRecord`
Represents a customer refund netting against an existing transaction.

```json
{
  "merchant_id": "CORP_01",
  "refund_id": "REF_7001",
  "transaction_id": "PAY_1001",
  "order_id": "ORD_5001",
  "amount": 50.00,
  "currency": "USD",
  "status": "SUCCEEDED",
  "timestamp": 1714503600
}
```

* **Primary Key:** `REC:REFUND:REF_7001`
* **Secondary Indexes:**
  * `IDX:ORDER:ORD_5001:REFUND:REF_7001`
  * `IDX:TXN:PAY_1001:REFUND:REF_7001`

---

### G. `FeePolicy`
Defines contractual rate formulas for gateway fee validation.

```json
{
  "policy_id": "STANDARD_CARD_2.0",
  "name": "Standard Card Rate",
  "processor": "STRIPE",
  "payment_method": "CREDIT_CARD",
  "currency": "USD",
  "percentage_rate": 2.0,
  "fixed_charge": 0.30
}
```

---

## 3. MiniVaultDB Storage Key Layout

| Key Prefix | Key Structure | Pointed Value |
| :--- | :--- | :--- |
| `REC:` | `REC:<RECORD_TYPE>:<ID>` | Full JSON payload |
| `IDX:ORDER:` | `IDX:ORDER:<order_id>:<TYPE>:<ID>` | `REC:<TYPE>:<ID>` pointer |
| `IDX:MERCHANT:` | `IDX:MERCHANT:<merchant_id>:<timestamp:010d>:<TYPE>:<ID>` | `REC:<TYPE>:<ID>` pointer |
| `IDX:BATCH:` | `IDX:BATCH:<batch_id>:PROCESSOR:<processor_id>` | `REC:PROCESSOR:<processor_id>` pointer |
| `IDX:REF:` | `IDX:REF:<clean_reference>:<TYPE>:<ID>` | `REC:<TYPE>:<ID>` pointer |
| `IDX:TXN:` | `IDX:TXN:<transaction_id>:SETTLEMENT:<settlement_id>` | `REC:SETTLEMENT:<settlement_id>` pointer |

