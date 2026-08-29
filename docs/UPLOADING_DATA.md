# Guide: Uploading Your Own Financial Data to VaultRecon AI

This guide explains how to import and reconcile custom CSV files using VaultRecon AI's [`GenericCSVAdapter`](file:///home/vishwa/Project/VaultRecon-AI/ingestion/adapters/generic_csv.py).

---

## 1. Supported Record Types

You can upload CSVs corresponding to any of the following financial scopes:

1. **`payments`**: Internal checkout, ledger, or billing payment records.
2. **`invoices`**: Accounts receivable or customer billing line items.
3. **`processors`**: Gateway transaction capture records (Stripe, Razorpay, etc.).
4. **`bank_txns`**: Bank statement credits or debits.
5. **`refunds`**: Chargebacks and customer refund lines.

> [!NOTE]
> **Important Limitation:** VaultRecon AI does **not** perform automatic AI-based schema guessing. You must define a clean `column_mapping` dictionary mapping your CSV headers to canonical fields.

---

## 2. Required & Optional Columns

### `PaymentRecord`
* **Required:** `transaction_id`, `amount`, `order_id`
* **Optional:** `merchant_id`, `customer_id`, `currency` (default: `"USD"`), `payment_method`, `timestamp`

### `InvoiceRecord`
* **Required:** `invoice_id`, `amount`, `order_id`
* **Optional:** `customer_id`, `currency`, `timestamp`

### `ProcessorTransaction`
* **Required:** `processor_transaction_id`, `gross_amount`, `order_id`
* **Optional:** `fee_amount`, `net_amount`, `currency`, `processor`, `timestamp`

### `BankTransactionRecord`
* **Required:** `bank_transaction_id`, `amount`, `reference`
* **Optional:** `currency`, `description`, `timestamp`

---

## 3. Example: Custom CSV Ingestion

Suppose you have two custom CSV files:

#### `my_orders.csv`
```csv
OrderNumber,PayRef,TotalCharged,CurrencyCode,DateUnix
ORD-901,TX-1001,150.00,USD,1714500000
ORD-902,TX-1002,275.50,USD,1714500300
```

#### `my_gateway.csv`
```csv
GatewayId,ReferenceOrder,GrossTotal,FeeDeducted,SettledDate
GATE-501,ORD-901,150.00,3.30,1714500000
GATE-502,ORD-902,275.50,5.81,1714500300
```

---

## 4. Python Code to Ingest and Reconcile

```python
from ingestion.adapters.generic_csv import GenericCSVAdapter
from recon.storage import MiniVaultDBClient
from ingestion.loader import IngestionLoader
from recon.matcher import ReconciliationEngine
from recon.rules import ReconciliationRules, FeePolicy

# 1. Define Column Mappings
mapping = {
    "payments": {
        "transaction_id": "PayRef",
        "order_id": "OrderNumber",
        "amount": "TotalCharged",
        "currency": "CurrencyCode",
        "timestamp": "DateUnix",
    },
    "processors": {
        "processor_transaction_id": "GatewayId",
        "order_id": "ReferenceOrder",
        "gross_amount": "GrossTotal",
        "fee_amount": "FeeDeducted",
        "timestamp": "SettledDate",
    }
}

# 2. Load Normalized Dataset
adapter = GenericCSVAdapter(
    file_paths={
        "payments": "my_orders.csv",
        "processors": "my_gateway.csv",
    },
    column_mappings=mapping,
)
dataset = adapter.load_dataset()

# 3. Store in MiniVaultDB & Reconcile
with MiniVaultDBClient(db_dir="./my_recon_vault") as db:
    # Ingest
    loader = IngestionLoader(db)
    loader.load_dataset(dataset)

    # Configure Rules
    rules = ReconciliationRules(amount_tolerance=0.05, timing_window_days=7)
    engine = ReconciliationEngine(db, rules=rules)

    # Execute Multi-Pass Reconciliation
    report = engine.reconcile_all(dataset.payments)

    print(f"Matched: {report.matched_count} / {report.total_evaluated}")
    print(f"Exceptions: {report.exception_count}")
```

---

## 5. Interpreting Reconciliation Output

* **`MATCHED` (`EXACT`)**: Same date, exact gross cents, contractual fee matches.
* **`MATCHED` (`TIMING`)**: Exact cents cleared within the allowed clearing window (T+1 to T+7 days).
* **`MATCHED` (`TOLERANCE`)**: Amount within configured penny tolerance ($\le \$0.05$).
* **`FEE_MISMATCH`**: Processor fee differs from contractual schedule. Handed to AI Controller.
* **`AMOUNT_MISMATCH`**: Gross difference exceeds tolerance.
* **`MISSING_PROCESSOR`**: Order recorded internally, but missing in external gateway feed.

