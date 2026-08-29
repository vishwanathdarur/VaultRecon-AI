"""
Generalized Staged Multi-Pass Reconciliation Engine for VaultRecon AI.
Executes multi-strategy deterministic reconciliation across:
- Level 1: Order / Transaction Scope (Internal Payment/Invoice <-> Processor / Bank Transaction)
  - Pass 1: EXACT MATCH (Exact Amount, Compatible Currency, Same Date)
  - Pass 2: TIMING MATCH (Exact Amount, Within Configurable Calendar Window +-N days)
  - Pass 3: TOLERANCE MATCH (Amount within tolerance <= tol, Within Window, High Description Similarity)
  - Pass 4: FUZZY CANDIDATE MATCH (Normalized text scoring & confidence thresholds)
- Level 2: Settlement Batch Scope (Settlement Batch Aggregate Net <-> Bank Payout)
- Level 3: Direct Settlement / Corporate Cash Ledger Scope
"""

import time
import uuid
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field

from recon.storage import MiniVaultDBClient
from recon.rules import (
    ReconciliationRules,
    GLOBAL_FEE_REGISTRY,
    MatchCandidate,
    calculate_description_similarity,
    normalize_description,
)
from recon.exceptions import FinancialException
from ingestion.schemas import (
    PaymentRecord,
    InvoiceRecord,
    ProcessorTransaction,
    SettlementRecord,
    SettlementBatch,
    BankTransactionRecord,
    RefundRecord,
    AdjustmentRecord,
)


@dataclass
class ReconciliationMatch:
    match_id: str
    scope: str  # ORDER, SETTLEMENT, BATCH
    work_key: str
    internal_payment_id: Optional[str] = None
    processor_transaction_id: Optional[str] = None
    settlement_batch_id: Optional[str] = None
    bank_entry_id: Optional[str] = None
    amount: float = 0.0
    fees: float = 0.0
    net_amount: float = 0.0
    confidence: float = 1.0
    reason_code: str = "EXACT_MATCH"
    match_strategy: str = "EXACT"  # EXACT, TIMING, TOLERANCE, FUZZY
    matched_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def payment_id(self) -> Optional[str]:
        return self.internal_payment_id or self.work_key


@dataclass
class MatcherReport:
    total_evaluated: int
    matched_count: int
    exception_count: int
    matches: List[ReconciliationMatch]
    exceptions: List[FinancialException]
    order_matches: List[ReconciliationMatch] = field(default_factory=list)
    batch_matches: List[ReconciliationMatch] = field(default_factory=list)
    duration_sec: float = 0.0
    throughput_records_per_sec: float = 0.0


class ReconciliationEngine:
    def __init__(self, db_client: MiniVaultDBClient, rules: Optional[ReconciliationRules] = None):
        self.db = db_client
        self.rules = rules or ReconciliationRules()
        self.consumed_target_ids: Set[str] = set()

    def reset_state(self):
        """Reset greedy 1:1 consumption state."""
        self.consumed_target_ids.clear()

    def reconcile_payment(self, pay: PaymentRecord) -> Tuple[Optional[ReconciliationMatch], Optional[FinancialException]]:
        """Alias for reconcile_order."""
        return self.reconcile_order(pay)

    def reconcile_all(self, payments: Optional[List[PaymentRecord]] = None) -> MatcherReport:
        """
        Run multi-source staged deterministic reconciliation across all stored payment records and batches.
        Uses bulk-indexed prefetching to eliminate O(N^2) repeated prefix scans.
        """
        self.reset_state()
        t_start = time.perf_counter()

        if payments is None:
            raw_payments = self.db.scan_prefix("REC:PAYMENT:")
            payments = []
            for _, val_json in raw_payments:
                payments.append(PaymentRecord.model_validate_json(val_json))

        # Bulk pre-fetch all secondary indexes in a single O(N) pass
        raw_order_indexes = self.db.scan_prefix("IDX:ORDER:")
        order_index_map: Dict[str, Dict[str, List[Tuple[str, str]]]] = {}
        for idx_key, pk_val in raw_order_indexes:
            parts = idx_key.split(":")
            if len(parts) >= 4:
                rec_type = parts[-2]
                oid = ":".join(parts[2:-2])
                order_index_map.setdefault(oid, {}).setdefault(rec_type, []).append((idx_key, pk_val))

        raw_ref_indexes = self.db.scan_prefix("IDX:REF:")
        ref_index_map: Dict[str, Dict[str, List[Tuple[str, str]]]] = {}
        for idx_key, pk_val in raw_ref_indexes:
            parts = idx_key.split(":")
            if len(parts) >= 4:
                rec_type = parts[-2]
                ref_code = ":".join(parts[2:-2])
                ref_index_map.setdefault(ref_code, {}).setdefault(rec_type, []).append((idx_key, pk_val))

        raw_txn_indexes = self.db.scan_prefix("IDX:TXN:")
        txn_settle_map: Dict[str, List[Tuple[str, str]]] = {}
        for idx_key, pk_val in raw_txn_indexes:
            parts = idx_key.split(":")
            if len(parts) >= 4 and parts[-2] == "SETTLEMENT":
                txn_id = ":".join(parts[2:-2])
                txn_settle_map.setdefault(txn_id, []).append((idx_key, pk_val))

        matches: List[ReconciliationMatch] = []
        exceptions: List[FinancialException] = []
        order_matches: List[ReconciliationMatch] = []
        batch_matches: List[ReconciliationMatch] = []

        # 1. Level 1: Order-Scope Staged Reconciliation
        for pay in payments:
            match_res, exc = self.reconcile_order(pay, order_index_map=order_index_map, txn_settle_map=txn_settle_map)
            if match_res:
                matches.append(match_res)
                order_matches.append(match_res)
            if exc:
                exceptions.append(exc)

        # Check for processor-only transactions (unrecorded bank charges / deposits)
        raw_processors = self.db.scan_prefix("REC:PROCESSOR:")
        for _, val_json in raw_processors:
            proc = ProcessorTransaction.model_validate_json(val_json)
            if proc.processor_transaction_id in self.consumed_target_ids:
                continue

            pay_indexes = order_index_map.get(proc.order_id, {}).get("PAYMENT", [])
            if not pay_indexes:
                exc = FinancialException(
                    exception_id=f"EXC_PROC_ONLY_{uuid.uuid4().hex[:8].upper()}",
                    merchant_id=proc.merchant_id,
                    exception_type="MISSING_INTERNAL",
                    primary_record_type="PROCESSOR",
                    primary_record_id=proc.processor_transaction_id,
                    related_record_ids=[proc.order_id],
                    expected_value=0.0,
                    actual_value=proc.gross_amount,
                    difference=proc.gross_amount,
                    status="OPEN",
                )
                exc.log_event("EXCEPTION_CREATED", "DETERMINISTIC_MATCHER", {
                    "reason": f"Bank/Processor transaction {proc.processor_transaction_id} ({proc.order_id}) has no corresponding internal GL/payment entry."
                })
                exceptions.append(exc)

        # 2. Level 2: Settlement Batch-Scope Reconciliation
        raw_batches = self.db.scan_prefix("REC:BATCH:")
        for _, val_json in raw_batches:
            batch = SettlementBatch.model_validate_json(val_json)
            b_match, b_exc = self.reconcile_batch(batch, ref_index_map=ref_index_map)
            if b_match:
                matches.append(b_match)
                batch_matches.append(b_match)
            if b_exc:
                exceptions.append(b_exc)

        t_end = time.perf_counter()
        dur = max(t_end - t_start, 1e-6)
        total = len(payments) + len(raw_batches)

        return MatcherReport(
            total_evaluated=total,
            matched_count=len(matches),
            exception_count=len(exceptions),
            matches=matches,
            exceptions=exceptions,
            order_matches=order_matches,
            batch_matches=batch_matches,
            duration_sec=dur,
            throughput_records_per_sec=round(total / dur, 2),
        )

    def reconcile_order(
        self,
        pay: PaymentRecord,
        order_index_map: Optional[Dict[str, Dict[str, List[Tuple[str, str]]]]] = None,
        txn_settle_map: Optional[Dict[str, List[Tuple[str, str]]]] = None,
    ) -> Tuple[Optional[ReconciliationMatch], Optional[FinancialException]]:
        """
        Level 1 Staged Reconciliation: Internal Payment/GL Entry <-> Processor Transaction / Bank Line.
        Evaluates multi-pass staged rules and collects all findings into a structured report.
        """
        order_id = pay.order_id
        findings: List[Dict[str, Any]] = []

        # Step 0: Check for Duplicate Internal Record Flag
        if pay.metadata.get("is_duplicate"):
            exc = FinancialException(
                exception_id=f"EXC_DUP_INT_{uuid.uuid4().hex[:8].upper()}",
                merchant_id=pay.merchant_id,
                exception_type="DUPLICATE_INTERNAL",
                primary_record_type="PAYMENT",
                primary_record_id=pay.transaction_id,
                related_record_ids=[order_id],
                expected_value=pay.amount,
                actual_value=pay.amount,
                difference=0.0,
                status="OPEN",
            )
            exc.log_event("EXCEPTION_CREATED", "DETERMINISTIC_MATCHER", {
                "reason": f"Duplicate internal payment/GL posting identifier for order/document {order_id}."
            })
            return None, exc

        pay_indexes = order_index_map.get(order_id, {}).get("PAYMENT", []) if order_index_map is not None else self.db.scan_prefix(f"IDX:ORDER:{order_id}:PAYMENT:")
        if len(pay_indexes) > 1 and self.rules.topology != "BANK_GL":
            exc = FinancialException(
                exception_id=f"EXC_DUP_INT_{uuid.uuid4().hex[:8].upper()}",
                merchant_id=pay.merchant_id,
                exception_type="DUPLICATE_INTERNAL",
                primary_record_type="PAYMENT",
                primary_record_id=pay.transaction_id,
                related_record_ids=[p[1] for p in pay_indexes],
                expected_value=pay.amount,
                actual_value=pay.amount,
                difference=0.0,
                status="OPEN",
            )
            exc.log_event("EXCEPTION_CREATED", "DETERMINISTIC_MATCHER", {
                "reason": f"Multiple internal payment records exist for order {order_id}."
            })
            return None, exc

        # Step 1: Check for Associated Refunds on this Order
        ref_indexes = order_index_map.get(order_id, {}).get("REFUND", []) if order_index_map is not None else self.db.scan_prefix(f"IDX:ORDER:{order_id}:REFUND:")
        if ref_indexes:
            raw_ref = self.db.get(ref_indexes[0][1])
            if raw_ref:
                ref_rec = RefundRecord.model_validate_json(raw_ref)
                exc_type = "PARTIAL_REFUND" if ref_rec.amount < pay.amount else "FULL_REFUND"
                findings.append({
                    "type": exc_type,
                    "expected": pay.amount,
                    "actual": ref_rec.amount,
                    "diff": round(pay.amount - ref_rec.amount, 2),
                    "related_ids": [ref_rec.refund_id, order_id],
                    "reason": f"Payment {pay.transaction_id} is associated with refund {ref_rec.refund_id} ({exc_type})."
                })

        # Step 1.5: Validate Invoice Gross Amount
        is_partial = str(pay.metadata.get("is_partial", "")).lower() in ("true", "1")
        inv_indexes = order_index_map.get(order_id, {}).get("INVOICE", []) if order_index_map is not None else self.db.scan_prefix(f"IDX:ORDER:{order_id}:INVOICE:")
        if inv_indexes:
            raw_inv = self.db.get(inv_indexes[0][1])
            if raw_inv:
                inv = InvoiceRecord.model_validate_json(raw_inv)
                if pay.amount > inv.amount + self.rules.amount_tolerance:
                    findings.append({
                        "type": "OVERPAYMENT",
                        "expected": inv.amount,
                        "actual": pay.amount,
                        "diff": round(pay.amount - inv.amount, 2),
                        "related_ids": [inv.invoice_id, order_id],
                        "reason": f"Payment amount {pay.amount} exceeds invoice total {inv.amount}."
                    })
                elif pay.amount < inv.amount - self.rules.amount_tolerance and not pay.metadata.get("is_partial"):
                    findings.append({
                        "type": "AMOUNT_MISMATCH",
                        "expected": inv.amount,
                        "actual": pay.amount,
                        "diff": round(inv.amount - pay.amount, 2),
                        "related_ids": [inv.invoice_id, order_id],
                        "reason": f"Payment amount {pay.amount} != Invoice amount {inv.amount}."
                    })

        # Step 2: Find Available (Unconsumed) Processor Transaction by Order ID
        proc_indexes = order_index_map.get(order_id, {}).get("PROCESSOR", []) if order_index_map is not None else self.db.scan_prefix(f"IDX:ORDER:{order_id}:PROCESSOR:")
        available_proc_indexes = [p for p in proc_indexes if p[1].split(":")[-1] not in self.consumed_target_ids]

        # Duplicate Processor Check
        if len(proc_indexes) > 1 and len(available_proc_indexes) > 1:
            findings.append({
                "type": "DUPLICATE_PROCESSOR",
                "expected": pay.amount,
                "actual": pay.amount,
                "diff": 0.0,
                "related_ids": [p[1] for p in proc_indexes],
                "reason": f"Multiple processor transactions found for order/doc {order_id}."
            })

        proc_txn: Optional[ProcessorTransaction] = None
        if available_proc_indexes:
            proc_pk = available_proc_indexes[0][1]
            raw_proc = self.db.get(proc_pk)
            if raw_proc:
                proc_txn = ProcessorTransaction.model_validate_json(raw_proc)

        # Fallback SettlementRecord index if stored under SETTLEMENT
        settle_record: Optional[SettlementRecord] = None
        if not proc_txn:
            if txn_settle_map is not None:
                settle_indexes = txn_settle_map.get(pay.transaction_id, []) or txn_settle_map.get(order_id, [])
            else:
                settle_indexes = self.db.scan_prefix(f"IDX:TXN:{pay.transaction_id}:SETTLEMENT:")
                if not settle_indexes:
                    settle_indexes = self.db.scan_prefix(f"IDX:TXN:{order_id}:SETTLEMENT:")
            avail_settle = [s for s in settle_indexes if s[1].split(":")[-1] not in self.consumed_target_ids]
            if avail_settle:
                set_pk = avail_settle[0][1]
                raw_set = self.db.get(set_pk)
                if raw_set:
                    settle_record = SettlementRecord.model_validate_json(raw_set)

        if not proc_txn and not settle_record:
            # If the transaction had duplicate internal copies and all targets are consumed
            pay_indexes = order_index_map.get(order_id, {}).get("PAYMENT", []) if order_index_map is not None else self.db.scan_prefix(f"IDX:ORDER:{order_id}:PAYMENT:")
            if len(pay_indexes) > 1:
                exc = FinancialException(
                    exception_id=f"EXC_DUP_INT_{uuid.uuid4().hex[:8].upper()}",
                    merchant_id=pay.merchant_id,
                    exception_type="DUPLICATE_INTERNAL",
                    primary_record_type="PAYMENT",
                    primary_record_id=pay.transaction_id,
                    related_record_ids=[p[1] for p in pay_indexes],
                    expected_value=pay.amount,
                    actual_value=pay.amount,
                    difference=0.0,
                    status="OPEN",
                )
                exc.log_event("EXCEPTION_CREATED", "DETERMINISTIC_MATCHER", {
                    "reason": f"Duplicate posting in ledger for order/document {order_id} (partner record already consumed)."
                })
                return None, exc

            findings.append({
                "type": "MISSING_PROCESSOR",
                "expected": pay.amount,
                "actual": 0.0,
                "diff": pay.amount,
                "related_ids": [order_id],
                "reason": f"No processor/bank transaction found for order/document {order_id} (outstanding check or deposit in transit)."
            })

        if not proc_txn and not settle_record:
            # Build exception from findings
            f0 = findings[0]
            exc = FinancialException(
                exception_id=f"EXC_{uuid.uuid4().hex[:8].upper()}",
                merchant_id=pay.merchant_id,
                exception_type=f0["type"],
                primary_record_type="PAYMENT",
                primary_record_id=pay.transaction_id,
                related_record_ids=f0["related_ids"],
                expected_value=f0["expected"],
                actual_value=f0["actual"],
                difference=f0["diff"],
                status="OPEN",
                metadata={"findings": findings},
            )
            exc.log_event("EXCEPTION_CREATED", "DETERMINISTIC_MATCHER", {"reason": f0["reason"], "all_findings": findings})
            return None, exc

        # Extract common fields
        proc_gross = proc_txn.gross_amount if proc_txn else settle_record.gross_amount
        proc_fee = proc_txn.fee_amount if proc_txn else settle_record.fees
        proc_net = proc_txn.net_amount if proc_txn else settle_record.net_amount
        proc_curr = proc_txn.currency if proc_txn else settle_record.currency
        proc_id = proc_txn.processor_transaction_id if proc_txn else settle_record.settlement_id
        proc_batch = proc_txn.settlement_batch_id if proc_txn else getattr(settle_record, "settlement_batch_id", None)
        proc_name = proc_txn.processor_name if proc_txn else "SETTLEMENT"
        proc_ts = proc_txn.timestamp if proc_txn else settle_record.timestamp
        proc_desc = proc_txn.metadata.get("Description", "") if proc_txn else ""

        # Step 3: Currency Check
        if not self.rules.is_currency_matching(pay.currency, proc_curr):
            findings.append({
                "type": "CURRENCY_MISMATCH",
                "expected": pay.currency,
                "actual": proc_curr,
                "diff": 0.0,
                "related_ids": [proc_id, order_id],
                "reason": f"Payment currency {pay.currency} != Processor currency {proc_curr}."
            })

        # Step 4: Staged Multi-Pass Matching Evaluation
        date_diff_days = abs(pay.timestamp - proc_ts) // 86400 if (pay.timestamp and proc_ts) else 0
        amount_diff = round(abs(pay.amount - proc_gross), 2)
        memo_text = pay.metadata.get("Memo", "")
        desc_sim = calculate_description_similarity(memo_text, proc_desc) if (memo_text and proc_desc) else 1.0

        match_strategy = None
        match_confidence = 1.0

        # Pass 1: EXACT MATCH (exact cents, exact date)
        if amount_diff <= 0.01 and date_diff_days == 0:
            match_strategy = "EXACT"
            match_confidence = 1.0

        # Pass 2: TIMING MATCH (exact cents, within timing window)
        elif amount_diff <= 0.01 and date_diff_days <= self.rules.timing_window_days:
            match_strategy = "TIMING"
            match_confidence = 0.98

        # Pass 3: TOLERANCE MATCH (small variance <= tolerance, within tolerance window, description or strong ref match)
        elif amount_diff <= self.rules.amount_tolerance and date_diff_days <= self.rules.tolerance_window_days:
            if desc_sim >= self.rules.fuzzy_threshold or (pay.order_id and pay.order_id == (proc_txn.order_id if proc_txn else "")):
                match_strategy = "TOLERANCE"
                match_confidence = 0.95
            else:
                findings.append({
                    "type": "AMOUNT_MISMATCH",
                    "expected": pay.amount,
                    "actual": proc_gross,
                    "diff": round(pay.amount - proc_gross, 2),
                    "related_ids": [proc_id, order_id],
                    "reason": f"Amount difference {amount_diff} exceeds tolerance or description similarity {desc_sim:.2f} is insufficient."
                })
        else:
            findings.append({
                "type": "AMOUNT_MISMATCH",
                "expected": pay.amount,
                "actual": proc_gross,
                "diff": round(pay.amount - proc_gross, 2),
                "related_ids": [proc_id, order_id],
                "reason": f"Payment gross {pay.amount} != Processor gross {proc_gross} (diff: {amount_diff}, date delta: {date_diff_days}d)."
            })

        # Step 5: Configurable Fee Policy Reconciliation (if topology requires fee check)
        if self.rules.enable_fee_validation and self.rules.topology != "BANK_GL":
            fee_policy_id = (
                (proc_txn.metadata.get("fee_policy_id") if proc_txn else None)
                or pay.metadata.get("fee_policy_id")
            )
            expected_fee = self.rules.compute_expected_fee(
                amount=pay.amount,
                payment_method=pay.payment_method,
                currency=pay.currency,
                merchant_id=pay.merchant_id,
                processor=proc_name,
                policy_id=fee_policy_id,
            )

            if expected_fee is None:
                findings.append({
                    "type": "UNKNOWN_FEE_POLICY",
                    "expected": 0.0,
                    "actual": proc_fee,
                    "diff": proc_fee,
                    "related_ids": [pay.transaction_id, order_id],
                    "reason": f"No contractual fee policy configured for payment method {pay.payment_method} ({pay.currency}) or policy ID '{fee_policy_id}'."
                })
            elif not self.rules.is_amount_matching(expected_fee, proc_fee):
                fee_diff = round(proc_fee - expected_fee, 2)
                findings.append({
                    "type": "FEE_MISMATCH",
                    "expected": expected_fee,
                    "actual": proc_fee,
                    "diff": fee_diff,
                    "related_ids": [pay.transaction_id, order_id],
                    "reason": f"Processor fee {proc_fee} differs from configured fee policy {expected_fee} (diff: {fee_diff})."
                })

        # Evaluate Aggregate Findings
        if findings:
            f0 = findings[0]
            exc = FinancialException(
                exception_id=f"EXC_{uuid.uuid4().hex[:8].upper()}",
                merchant_id=pay.merchant_id,
                exception_type=f0["type"],
                primary_record_type="PROCESSOR" if proc_txn else "PAYMENT",
                primary_record_id=proc_id if proc_txn else pay.transaction_id,
                related_record_ids=f0["related_ids"],
                expected_value=f0["expected"],
                actual_value=f0["actual"],
                difference=f0["diff"],
                status="OPEN",
                metadata={"findings": findings, "finding_count": len(findings)},
            )
            exc.log_event("EXCEPTION_CREATED", "DETERMINISTIC_MATCHER", {
                "primary_reason": f0["reason"],
                "all_findings": findings,
            })
            return None, exc

        # Deterministic Match Success
        reason = "PARTIAL_PAYMENT_MATCH" if is_partial else f"L1_{match_strategy}_ORDER_MATCH"
        match = ReconciliationMatch(
            match_id=f"MATCH_ORD_{uuid.uuid4().hex[:8].upper()}",
            scope="ORDER",
            work_key=order_id,
            internal_payment_id=pay.transaction_id,
            processor_transaction_id=proc_id,
            settlement_batch_id=proc_batch,
            amount=pay.amount,
            fees=proc_fee,
            net_amount=proc_net,
            confidence=match_confidence,
            reason_code=reason,
            match_strategy=match_strategy or "EXACT",
            metadata={
                "is_partial": is_partial,
                "date_diff_days": date_diff_days,
                "amount_diff": amount_diff,
                "desc_similarity": desc_sim,
            },
        )

        # Mark target record as consumed for greedy 1:1 matching
        self.consumed_target_ids.add(proc_id)
        return match, None

    def reconcile_batch(
        self,
        batch: SettlementBatch,
        ref_index_map: Optional[Dict[str, Dict[str, List[Tuple[str, str]]]]] = None,
    ) -> Tuple[Optional[ReconciliationMatch], Optional[FinancialException]]:
        """
        Level 2 Reconciliation: Settlement Batch Aggregated Net <-> Bank Payout Transaction.
        """
        batch_id = batch.batch_id

        # Step 1: Find Bank Transaction referencing this batch
        clean_ref = "".join(c for c in batch_id.upper() if c.isalnum() or c in ("-", "_"))
        if ref_index_map is not None:
            bank_indexes = ref_index_map.get(clean_ref, {}).get("BANK", [])
        else:
            bank_indexes = self.db.scan_prefix(f"IDX:REF:{clean_ref}:BANK:")

        if len(bank_indexes) > 1:
            exc = FinancialException(
                exception_id=f"EXC_DUP_BANK_{uuid.uuid4().hex[:8].upper()}",
                merchant_id=batch.merchant_id,
                exception_type="DUPLICATE_BANK_ENTRY",
                primary_record_type="BATCH",
                primary_record_id=batch_id,
                related_record_ids=[b[1] for b in bank_indexes],
                expected_value=batch.total_net,
                actual_value=batch.total_net,
                difference=0.0,
                status="OPEN",
            )
            exc.log_event("EXCEPTION_CREATED", "DETERMINISTIC_MATCHER", {
                "reason": f"Multiple bank deposit entries reference settlement batch {batch_id}."
            })
            return None, exc

        bank_txn: Optional[BankTransactionRecord] = None
        if bank_indexes:
            raw_bank = self.db.get(bank_indexes[0][1])
            if raw_bank:
                bank_txn = BankTransactionRecord.model_validate_json(raw_bank)

        if not bank_txn:
            exc = FinancialException(
                exception_id=f"EXC_BATCH_{uuid.uuid4().hex[:8].upper()}",
                merchant_id=batch.merchant_id,
                exception_type="MISSING_BANK_SETTLEMENT",
                primary_record_type="BATCH",
                primary_record_id=batch_id,
                expected_value=batch.total_net,
                actual_value=0.0,
                difference=batch.total_net,
                status="OPEN",
            )
            exc.log_event("EXCEPTION_CREATED", "DETERMINISTIC_MATCHER", {
                "reason": f"No bank deposit entry found referencing settlement batch {batch_id}."
            })
            return None, exc

        # Step 2: Currency Check
        if not self.rules.is_currency_matching(batch.currency, bank_txn.currency):
            exc = FinancialException(
                exception_id=f"EXC_BATCH_{uuid.uuid4().hex[:8].upper()}",
                merchant_id=batch.merchant_id,
                exception_type="CURRENCY_MISMATCH",
                primary_record_type="BATCH",
                primary_record_id=batch_id,
                related_record_ids=[bank_txn.bank_transaction_id],
                expected_value=batch.currency,
                actual_value=bank_txn.currency,
                difference=0.0,
                status="OPEN",
            )
            return None, exc

        # Step 3: Amount Check
        if not self.rules.is_amount_matching(batch.total_net, bank_txn.amount, tolerance=self.rules.amount_tolerance):
            diff = round(batch.total_net - bank_txn.amount, 2)
            exc = FinancialException(
                exception_id=f"EXC_BATCH_{uuid.uuid4().hex[:8].upper()}",
                merchant_id=batch.merchant_id,
                exception_type="AMOUNT_MISMATCH",
                primary_record_type="BATCH",
                primary_record_id=batch_id,
                related_record_ids=[bank_txn.bank_transaction_id],
                expected_value=batch.total_net,
                actual_value=bank_txn.amount,
                difference=diff,
                status="OPEN",
            )
            exc.log_event("EXCEPTION_CREATED", "DETERMINISTIC_MATCHER", {
                "reason": f"Settlement batch net sum {batch.total_net} != Bank payout amount {bank_txn.amount}."
            })
            return None, exc

        # Step 4: Time Window / Late Settlement Check (e.g. > 72 hours)
        if not self.rules.is_within_time_window(batch.timestamp, bank_txn.timestamp):
            exc = FinancialException(
                exception_id=f"EXC_BATCH_{uuid.uuid4().hex[:8].upper()}",
                merchant_id=batch.merchant_id,
                exception_type="LATE_SETTLEMENT",
                primary_record_type="BATCH",
                primary_record_id=batch_id,
                related_record_ids=[bank_txn.bank_transaction_id],
                expected_value=batch.timestamp,
                actual_value=bank_txn.timestamp,
                difference=abs(batch.timestamp - bank_txn.timestamp),
                status="OPEN",
            )
            exc.log_event("EXCEPTION_CREATED", "DETERMINISTIC_MATCHER", {
                "reason": f"Settlement payout received outside normal SLA settlement window."
            })
            return None, exc

        # Deterministic Match for Batch Scope
        match = ReconciliationMatch(
            match_id=f"MATCH_BATCH_{uuid.uuid4().hex[:8].upper()}",
            scope="SETTLEMENT",
            work_key=batch_id,
            settlement_batch_id=batch_id,
            bank_entry_id=bank_txn.bank_transaction_id,
            amount=batch.total_gross,
            fees=batch.total_fees,
            net_amount=batch.total_net,
            confidence=1.0,
            reason_code="L2_EXACT_SETTLEMENT_MATCH",
            match_strategy="EXACT",
        )
        return match, None
