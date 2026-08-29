"""
Default Synthetic Financial Dataset Generator for VaultRecon AI.
Generates reproducible, multi-source financial lifecycle records covering all supported
reconciliation scenarios (exact matches, timing lags, penny tolerances, fuzzy descriptions,
fee discrepancies, refunds, duplicates, and settlement batch relationships).
"""

import random
import time
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field

from ingestion.adapters.base import NormalizedDataset
from ingestion.schemas import (
    PaymentRecord,
    InvoiceRecord,
    ProcessorTransaction,
    SettlementBatch,
    BankTransactionRecord,
    RefundRecord,
    FeePolicy,
)


class DefaultDatasetGenerator:
    def __init__(self, seed: int = 42, base_time: int = 1714500000):
        self.seed = seed
        self.rng = random.Random(seed)
        self.base_time = base_time  # 2024-05-01 00:00:00 UTC

    def generate(self, count: int = 100) -> NormalizedDataset:
        """
        Generate `count` multi-source financial lifecycle cases.
        """
        dataset = NormalizedDataset(source_name=f"DefaultSynthetic_{count}")

        # 1. Register Standard & Surcharge Fee Policies
        std_card = FeePolicy(
            policy_id="STANDARD_CARD_2.0",
            name="Standard Credit Card Fee (2.0%)",
            percentage_rate=2.0,
            fixed_charge=0.0,
            payment_method="CREDIT_CARD",
            currency="USD",
        )
        intl_card = FeePolicy(
            policy_id="RULE_INTL_CARD_3.5",
            name="International Premium Card Surcharge (3.5%)",
            percentage_rate=3.5,
            fixed_charge=0.0,
            payment_method="INTERNATIONAL_CARD",
            currency="USD",
        )
        upi_free = FeePolicy(
            policy_id="ZERO_FEE_DIRECT",
            name="Direct Debit Zero Fee",
            percentage_rate=0.0,
            fixed_charge=0.0,
            payment_method="UPI",
            currency="USD",
        )
        dataset.fee_policies.extend([std_card, intl_card, upi_free])

        # Batch grouping accumulators
        batch_txns: List[str] = []
        batch_gross = 0.0
        batch_net = 0.0
        current_batch_num = 1

        for i in range(1, count + 1):
            ts = self.base_time + (i * 300)
            order_id = f"ORD_{10000 + i}"
            pay_id = f"PAY_{20000 + i}"
            inv_id = f"INV_{30000 + i}"
            proc_id = f"PROC_{40000 + i}"
            cust_id = f"CUST_{self.rng.randint(1000, 9999)}"
            merchant_id = "CORP_OPERATING"

            amount = round(self.rng.uniform(25.0, 2500.0), 2)
            scenario_rand = self.rng.random()

            # SCENARIO 1: Clean Exact Match (70% probability)
            if scenario_rand < 0.70:
                fee = std_card.calculate_fee(amount)
                net = std_card.calculate_net(amount)

                pay = PaymentRecord(merchant_id=merchant_id, transaction_id=pay_id, order_id=order_id, customer_id=cust_id, amount=amount, currency="USD", payment_method="CREDIT_CARD", timestamp=ts)
                inv = InvoiceRecord(merchant_id=merchant_id, invoice_id=inv_id, order_id=order_id, customer_id=cust_id, amount=amount, currency="USD", timestamp=ts)
                proc = ProcessorTransaction(merchant_id=merchant_id, processor_transaction_id=proc_id, order_id=order_id, gross_amount=amount, fee_amount=fee, net_amount=net, currency="USD", timestamp=ts)

                dataset.payments.append(pay)
                dataset.invoices.append(inv)
                dataset.processor_transactions.append(proc)
                dataset.ground_truth.append({"id": pay_id, "order_id": order_id, "scenario": "EXACT_MATCH", "expected": "MATCHED", "is_match": True})

                batch_txns.append(proc_id)
                batch_gross += amount
                batch_net += net

            # SCENARIO 2: Timing Lag Match (T+1 to T+3 days) (8% probability)
            elif scenario_rand < 0.78:
                lag_days = self.rng.randint(1, 3)
                proc_ts = ts + (lag_days * 86400)
                fee = std_card.calculate_fee(amount)
                net = std_card.calculate_net(amount)

                pay = PaymentRecord(merchant_id=merchant_id, transaction_id=pay_id, order_id=order_id, customer_id=cust_id, amount=amount, currency="USD", payment_method="CREDIT_CARD", timestamp=ts)
                inv = InvoiceRecord(merchant_id=merchant_id, invoice_id=inv_id, order_id=order_id, customer_id=cust_id, amount=amount, currency="USD", timestamp=ts)
                proc = ProcessorTransaction(merchant_id=merchant_id, processor_transaction_id=proc_id, order_id=order_id, gross_amount=amount, fee_amount=fee, net_amount=net, currency="USD", timestamp=proc_ts)

                dataset.payments.append(pay)
                dataset.invoices.append(inv)
                dataset.processor_transactions.append(proc)
                dataset.ground_truth.append({"id": pay_id, "order_id": order_id, "scenario": "TIMING_MATCH", "expected": "MATCHED", "is_match": True})

                batch_txns.append(proc_id)
                batch_gross += amount
                batch_net += net

            # SCENARIO 3: Penny Tolerance Match (diff <= $0.03) (5% probability)
            elif scenario_rand < 0.83:
                proc_amt = round(amount + self.rng.choice([0.01, 0.02, -0.01, -0.02]), 2)
                fee = std_card.calculate_fee(proc_amt)
                net = std_card.calculate_net(proc_amt)

                pay = PaymentRecord(merchant_id=merchant_id, transaction_id=pay_id, order_id=order_id, customer_id=cust_id, amount=amount, currency="USD", payment_method="CREDIT_CARD", timestamp=ts)
                inv = InvoiceRecord(merchant_id=merchant_id, invoice_id=inv_id, order_id=order_id, customer_id=cust_id, amount=amount, currency="USD", timestamp=ts)
                proc = ProcessorTransaction(merchant_id=merchant_id, processor_transaction_id=proc_id, order_id=order_id, gross_amount=proc_amt, fee_amount=fee, net_amount=net, currency="USD", timestamp=ts)

                dataset.payments.append(pay)
                dataset.invoices.append(inv)
                dataset.processor_transactions.append(proc)
                dataset.ground_truth.append({"id": pay_id, "order_id": order_id, "scenario": "TOLERANCE_MATCH", "expected": "MATCHED", "is_match": True})

            # SCENARIO 4: Resolvable International Card Surcharge (4% probability)
            elif scenario_rand < 0.87:
                fee = round(amount * 0.035, 2)
                net = round(amount - fee, 2)

                pay = PaymentRecord(merchant_id=merchant_id, transaction_id=pay_id, order_id=order_id, customer_id=cust_id, amount=amount, currency="USD", payment_method="INTERNATIONAL_CARD", timestamp=ts)
                inv = InvoiceRecord(merchant_id=merchant_id, invoice_id=inv_id, order_id=order_id, customer_id=cust_id, amount=amount, currency="USD", timestamp=ts)
                proc = ProcessorTransaction(merchant_id=merchant_id, processor_transaction_id=proc_id, order_id=order_id, gross_amount=amount, fee_amount=fee, net_amount=net, currency="USD", timestamp=ts)

                dataset.payments.append(pay)
                dataset.invoices.append(inv)
                dataset.processor_transactions.append(proc)
                dataset.ground_truth.append({"id": pay_id, "order_id": order_id, "scenario": "FEE_MISMATCH_RESOLVABLE", "expected": "AI_RESOLVED", "is_match": True})

            # SCENARIO 5: Unresolvable Fee Markup (4% probability)
            elif scenario_rand < 0.91:
                unexplained_fee = round(amount * 0.15 + 10.0, 2)
                net = round(amount - unexplained_fee, 2)

                pay = PaymentRecord(merchant_id=merchant_id, transaction_id=pay_id, order_id=order_id, customer_id=cust_id, amount=amount, currency="USD", payment_method="CREDIT_CARD", timestamp=ts)
                inv = InvoiceRecord(merchant_id=merchant_id, invoice_id=inv_id, order_id=order_id, customer_id=cust_id, amount=amount, currency="USD", timestamp=ts)
                proc = ProcessorTransaction(merchant_id=merchant_id, processor_transaction_id=proc_id, order_id=order_id, gross_amount=amount, fee_amount=unexplained_fee, net_amount=net, currency="USD", timestamp=ts)

                dataset.payments.append(pay)
                dataset.invoices.append(inv)
                dataset.processor_transactions.append(proc)
                dataset.ground_truth.append({"id": pay_id, "order_id": order_id, "scenario": "FEE_MISMATCH_UNRESOLVABLE", "expected": "HUMAN_REVIEW", "is_match": False})

            # SCENARIO 6: Gross Amount Mismatch (3% probability)
            elif scenario_rand < 0.94:
                inv_amt = round(amount + 75.0, 2)
                fee = std_card.calculate_fee(amount)
                net = std_card.calculate_net(amount)

                pay = PaymentRecord(merchant_id=merchant_id, transaction_id=pay_id, order_id=order_id, customer_id=cust_id, amount=amount, currency="USD", payment_method="CREDIT_CARD", timestamp=ts)
                inv = InvoiceRecord(merchant_id=merchant_id, invoice_id=inv_id, order_id=order_id, customer_id=cust_id, amount=inv_amt, currency="USD", timestamp=ts)
                proc = ProcessorTransaction(merchant_id=merchant_id, processor_transaction_id=proc_id, order_id=order_id, gross_amount=amount, fee_amount=fee, net_amount=net, currency="USD", timestamp=ts)

                dataset.payments.append(pay)
                dataset.invoices.append(inv)
                dataset.processor_transactions.append(proc)
                dataset.ground_truth.append({"id": pay_id, "order_id": order_id, "scenario": "AMOUNT_MISMATCH", "expected": "HUMAN_REVIEW", "is_match": False})

            # SCENARIO 7: Missing Gateway Transaction (3% probability)
            elif scenario_rand < 0.97:
                pay = PaymentRecord(merchant_id=merchant_id, transaction_id=pay_id, order_id=order_id, customer_id=cust_id, amount=amount, currency="USD", payment_method="CREDIT_CARD", timestamp=ts)
                inv = InvoiceRecord(merchant_id=merchant_id, invoice_id=inv_id, order_id=order_id, customer_id=cust_id, amount=amount, currency="USD", timestamp=ts)

                dataset.payments.append(pay)
                dataset.invoices.append(inv)
                dataset.ground_truth.append({"id": pay_id, "order_id": order_id, "scenario": "MISSING_PROCESSOR", "expected": "HUMAN_REVIEW", "is_match": False})

            # SCENARIO 8: Partial Refund Discrepancy (3% probability)
            else:
                ref_amt = round(amount * 0.40, 2)
                ref_id = f"REF_{50000 + i}"
                fee = std_card.calculate_fee(amount)
                net = std_card.calculate_net(amount)

                pay = PaymentRecord(merchant_id=merchant_id, transaction_id=pay_id, order_id=order_id, customer_id=cust_id, amount=amount, currency="USD", payment_method="CREDIT_CARD", timestamp=ts)
                inv = InvoiceRecord(merchant_id=merchant_id, invoice_id=inv_id, order_id=order_id, customer_id=cust_id, amount=amount, currency="USD", timestamp=ts)
                proc = ProcessorTransaction(merchant_id=merchant_id, processor_transaction_id=proc_id, order_id=order_id, gross_amount=amount, fee_amount=fee, net_amount=net, currency="USD", timestamp=ts)
                refund = RefundRecord(merchant_id=merchant_id, refund_id=ref_id, transaction_id=pay_id, order_id=order_id, amount=ref_amt, currency="USD", timestamp=ts + 3600)

                dataset.payments.append(pay)
                dataset.invoices.append(inv)
                dataset.processor_transactions.append(proc)
                dataset.refunds.append(refund)
                dataset.ground_truth.append({"id": pay_id, "order_id": order_id, "scenario": "PARTIAL_REFUND", "expected": "HUMAN_REVIEW", "is_match": False})

            # Periodic Settlement Batch creation (every 10 transactions)
            if len(batch_txns) >= 10 or i == count:
                if batch_txns:
                    batch_id = f"BATCH_{current_batch_num:04d}"
                    bnk_id = f"BNK_DEP_{current_batch_num:04d}"
                    b_net = round(batch_net, 2)
                    b_gross = round(batch_gross, 2)

                    batch = SettlementBatch(
                        merchant_id=merchant_id,
                        batch_id=batch_id,
                        total_gross=b_gross,
                        total_net=b_net,
                        transaction_count=len(batch_txns),
                        transaction_ids=list(batch_txns),
                        timestamp=ts + 86400,
                    )
                    bank = BankTransactionRecord(
                        merchant_id=merchant_id,
                        bank_transaction_id=bnk_id,
                        reference=batch_id,
                        amount=b_net,
                        currency="USD",
                        timestamp=ts + 86400 + 7200,
                        description=f"Direct Deposit Payout {batch_id}",
                    )
                    dataset.batches.append(batch)
                    dataset.bank_transactions.append(bank)

                    batch_txns = []
                    batch_gross = 0.0
                    batch_net = 0.0
                    current_batch_num += 1

        return dataset

