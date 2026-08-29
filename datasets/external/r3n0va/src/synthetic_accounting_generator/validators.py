from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Iterator

from .utils import LEGAL_NAME_SUFFIXES


def iter_csv(input_dir: Path, name: str) -> Iterator[dict[str, str]]:
    path = input_dir / f"{name}.csv"
    if not path.exists():
        return iter(())
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            yield row


def read_csv(input_dir: Path, name: str) -> list[dict[str, str]]:
    return list(iter_csv(input_dir, name))


def as_bool(value: str) -> bool:
    return value.strip().lower() in {"true", "1", "yes"}


def as_date(value: str) -> date | None:
    return date.fromisoformat(value) if value else None


def as_datetime(value: str) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def validate_dataset(input_dir: Path) -> dict:
    checks: list[dict] = []

    def add(
        name: str,
        passed: bool,
        details: str,
        failure_severity: str = "ERROR",
    ) -> None:
        checks.append({
            "check_name": name,
            "passed": bool(passed),
            "details": details,
            "failure_severity": failure_severity,
        })

    dq_rows = read_csv(input_dir, "dq_issue_manifest")
    expected_issues = {
        (
            row["table_name"],
            row["record_id"],
            row["rule_code"],
        )
        for row in dq_rows
        if as_bool(row.get("expected_issue", "False"))
    }

    def expected(
        table_name: str,
        record_id: str,
        rule_code: str,
    ) -> bool:
        return (table_name, record_id, rule_code) in expected_issues

    regions = read_csv(input_dir, "region")
    cities = read_csv(input_dir, "city")
    legal_forms = read_csv(input_dir, "legal_form")
    industries = read_csv(input_dir, "industry")
    currencies = read_csv(input_dir, "currency")
    service_types = read_csv(input_dir, "service_type")
    document_types = read_csv(input_dir, "document_type")
    task_types = read_csv(input_dir, "task_type")
    gl_accounts = read_csv(input_dir, "gl_account")

    firms = read_csv(input_dir, "accounting_firm")
    offices = read_csv(input_dir, "office")
    employees = read_csv(input_dir, "employee")
    clients = read_csv(input_dir, "client_company")
    contacts = read_csv(input_dir, "client_contact")
    client_events = read_csv(input_dir, "client_event")
    assignments = read_csv(input_dir, "client_assignment")
    contracts = read_csv(input_dir, "service_contract")
    contract_services = read_csv(input_dir, "contract_service")
    bank_accounts = read_csv(input_dir, "bank_account")
    counterparties = read_csv(input_dir, "counterparty")

    required_nonempty = {
        "accounting_firm": firms,
        "office": offices,
        "employee": employees,
        "client_company": clients,
        "service_contract": contracts,
    }
    for table, table_rows in required_nonempty.items():
        add(
            f"{table}_nonempty",
            bool(table_rows),
            f"{len(table_rows)} rows",
        )

    region_ids = {row["region_code"] for row in regions}
    city_ids = {row["city_code"] for row in cities}
    legal_form_ids = {row["legal_form_code"] for row in legal_forms}
    industry_ids = {row["industry_code"] for row in industries}
    currency_ids = {row["currency_code"] for row in currencies}
    service_type_ids = {
        row["service_type_code"] for row in service_types
    }
    document_type_ids = {
        row["document_type_code"] for row in document_types
    }
    task_type_ids = {row["task_type_code"] for row in task_types}
    gl_account_ids = {row["gl_account_code"] for row in gl_accounts}

    add(
        "city_region_fk",
        all(row["region_code"] in region_ids for row in cities),
        "city → region",
    )

    firm_by_id = {row["firm_id"]: row for row in firms}
    office_by_id = {row["office_id"]: row for row in offices}
    employee_by_id = {row["employee_id"]: row for row in employees}
    client_by_id = {row["client_id"]: row for row in clients}
    contract_by_id = {row["contract_id"]: row for row in contracts}
    bank_account_by_id = {
        row["bank_account_id"]: row for row in bank_accounts
    }
    counterparty_by_id = {
        row["counterparty_id"]: row for row in counterparties
    }

    add(
        "firm_headquarters_city_fk",
        all(
            row["headquarters_city_code"] in city_ids
            for row in firms
        ),
        "firm → headquarters city",
    )
    add(
        "office_firm_fk",
        all(row["firm_id"] in firm_by_id for row in offices),
        "office → firm",
    )
    add(
        "office_city_fk",
        all(row["city_code"] in city_ids for row in offices),
        "office → city",
    )

    office_date_errors = 0
    for office in offices:
        firm = firm_by_id.get(office["firm_id"])
        if firm and as_date(office["opened_date"]) < as_date(
            firm["founded_date"]
        ):
            office_date_errors += 1
    add(
        "office_opened_after_firm_founded",
        office_date_errors == 0,
        f"{office_date_errors} invalid office dates",
    )

    add(
        "employee_firm_fk",
        all(row["firm_id"] in firm_by_id for row in employees),
        "employee → firm",
    )
    add(
        "employee_office_fk",
        all(row["office_id"] in office_by_id for row in employees),
        "employee → office",
    )
    add(
        "employee_office_same_firm",
        all(
            row["office_id"] in office_by_id
            and office_by_id[row["office_id"]]["firm_id"]
            == row["firm_id"]
            for row in employees
        ),
        "employee office belongs to employee firm",
    )

    allowed_roles = {"HEAD", "CM_JR", "CM_SR", "ACC_JR", "ACC_SR"}
    add(
        "employee_role_scope",
        all(row["role_code"] in allowed_roles for row in employees),
        "only agreed employee roles",
    )
    add(
        "permanent_active_employment",
        all(
            row["contract_type"] == "PERMANENT"
            and not row["employment_end_date"]
            for row in employees
        ),
        "all employees are active permanent employees",
    )

    employee_date_errors = 0
    for employee in employees:
        firm = firm_by_id.get(employee["firm_id"])
        if firm and as_date(employee["employment_start_date"]) < as_date(
            firm["founded_date"]
        ):
            employee_date_errors += 1
    add(
        "employee_started_after_firm_founded",
        employee_date_errors == 0,
        f"{employee_date_errors} invalid employment dates",
    )

    employee_emails = [row["email"] for row in employees]
    add(
        "employee_email_uniqueness",
        len(employee_emails) == len(set(employee_emails)),
        f"{len(employee_emails) - len(set(employee_emails))} duplicates",
    )

    add(
        "client_firm_fk",
        all(row["firm_id"] in firm_by_id for row in clients),
        "client → firm",
    )
    add(
        "client_office_fk",
        all(row["primary_office_id"] in office_by_id for row in clients),
        "client → primary office",
    )
    add(
        "client_office_same_firm",
        all(
            row["primary_office_id"] in office_by_id
            and office_by_id[row["primary_office_id"]]["firm_id"]
            == row["firm_id"]
            for row in clients
        ),
        "client primary office belongs to accounting firm",
    )
    add(
        "client_legal_form_fk",
        all(row["legal_form_code"] in legal_form_ids for row in clients),
        "client → legal form",
    )
    add(
        "client_industry_fk",
        all(row["industry_code"] in industry_ids for row in clients),
        "client → industry",
    )
    add(
        "client_city_fk",
        all(row["city_code"] in city_ids for row in clients),
        "client → city",
    )
    add(
        "client_base_currency_fk",
        all(row["base_currency"] in currency_ids for row in clients),
        "client → base currency",
    )

    company_names = [row["company_name"] for row in clients]
    add(
        "client_company_name_uniqueness",
        len(company_names) == len(set(company_names)),
        f"{len(company_names) - len(set(company_names))} duplicates",
    )

    explicit_suffixes = {
        suffix
        for code, suffix in LEGAL_NAME_SUFFIXES.items()
        if code != "EU" and suffix
    }
    suffix_errors = 0
    for client in clients:
        expected_suffix = LEGAL_NAME_SUFFIXES[
            client["legal_form_code"]
        ]
        name = client["company_name"]
        if expected_suffix:
            if not name.endswith(expected_suffix):
                suffix_errors += 1
        elif any(name.endswith(suffix) for suffix in explicit_suffixes):
            suffix_errors += 1
    add(
        "company_name_legal_form_consistency",
        suffix_errors == 0,
        f"{suffix_errors} inconsistent company names",
    )

    non_registered_with_vat_id = [
        row["client_id"]
        for row in clients
        if not as_bool(row["vat_registered"]) and row["vat_id"]
    ]
    add(
        "non_registered_clients_have_no_vat_id",
        not non_registered_with_vat_id,
        f"{len(non_registered_with_vat_id)} violations",
    )

    unexplained_missing_vat_ids = [
        row["client_id"]
        for row in clients
        if as_bool(row["vat_registered"])
        and not row["vat_id"]
        and not expected(
            "client_company",
            row["client_id"],
            "MISSING_VAT_ID",
        )
    ]
    add(
        "registered_clients_have_vat_id_or_expected_dq",
        not unexplained_missing_vat_ids,
        f"{len(unexplained_missing_vat_ids)} unexplained missing VAT IDs",
    )

    vat_ids = [
        row["vat_id"] for row in clients if row["vat_id"]
    ]
    add(
        "vat_id_uniqueness",
        len(vat_ids) == len(set(vat_ids)),
        f"{len(vat_ids) - len(set(vat_ids))} duplicates",
    )

    client_date_errors = 0
    for client in clients:
        incorporation = as_date(client["incorporation_date"])
        onboarding = as_date(client["onboarding_date"])
        termination = as_date(client["termination_date"])
        if incorporation > onboarding:
            client_date_errors += 1
        if termination and termination < onboarding:
            client_date_errors += 1
        if (
            client["lifecycle_status"] == "TERMINATED"
            and termination is None
        ):
            client_date_errors += 1
        if (
            client["lifecycle_status"] != "TERMINATED"
            and termination is not None
        ):
            client_date_errors += 1
    add(
        "client_lifecycle_date_order",
        client_date_errors == 0,
        f"{client_date_errors} invalid client date sequences",
    )

    add(
        "contact_client_fk",
        all(row["client_id"] in client_by_id for row in contacts),
        "contact → client",
    )
    contact_emails = [row["email"] for row in contacts]
    add(
        "client_contact_email_uniqueness",
        len(contact_emails) == len(set(contact_emails)),
        f"{len(contact_emails) - len(set(contact_emails))} duplicates",
    )

    event_errors = 0
    for event in client_events:
        client = client_by_id.get(event["client_id"])
        if not client:
            event_errors += 1
            continue
        event_date = as_date(event["event_date"])
        onboarding = as_date(client["onboarding_date"])
        termination = as_date(client["termination_date"])
        if event_date < onboarding:
            event_errors += 1
        if termination and event_date > termination:
            event_errors += 1
        if (
            event["event_type"] == "CONTRACT_TERMINATED"
            and event_date != termination
        ):
            event_errors += 1
    add(
        "client_event_lifecycle_consistency",
        event_errors == 0,
        f"{event_errors} invalid lifecycle events",
    )

    add(
        "assignment_client_fk",
        all(row["client_id"] in client_by_id for row in assignments),
        "assignment → client",
    )
    add(
        "assignment_employee_fk",
        all(
            row["client_manager_id"] in employee_by_id
            and row["accountant_id"] in employee_by_id
            for row in assignments
        ),
        "assignment → employees",
    )

    assignment_role_errors = 0
    assignment_firm_errors = 0
    for assignment in assignments:
        client = client_by_id.get(assignment["client_id"])
        manager = employee_by_id.get(
            assignment["client_manager_id"]
        )
        accountant = employee_by_id.get(
            assignment["accountant_id"]
        )
        if manager and manager["role_code"] not in {"CM_JR", "CM_SR"}:
            assignment_role_errors += 1
        if accountant and accountant["role_code"] not in {
            "ACC_JR",
            "ACC_SR",
        }:
            assignment_role_errors += 1
        if client and manager and manager["firm_id"] != client["firm_id"]:
            assignment_firm_errors += 1
        if (
            client
            and accountant
            and accountant["firm_id"] != client["firm_id"]
        ):
            assignment_firm_errors += 1
    add(
        "assignment_role_consistency",
        assignment_role_errors == 0,
        f"{assignment_role_errors} invalid employee roles",
    )
    add(
        "assignment_firm_consistency",
        assignment_firm_errors == 0,
        f"{assignment_firm_errors} cross-firm assignments",
    )
    add(
        "one_current_assignment_per_client",
        len(assignments)
        == len({row["client_id"] for row in assignments})
        == len(clients),
        f"{len(assignments)} assignments for {len(clients)} clients",
    )

    contract_errors = 0
    for contract in contracts:
        client = client_by_id.get(contract["client_id"])
        if not client:
            contract_errors += 1
            continue
        if contract["firm_id"] != client["firm_id"]:
            contract_errors += 1
        if contract["start_date"] != client["onboarding_date"]:
            contract_errors += 1
        if contract["end_date"] != client["termination_date"]:
            contract_errors += 1
        if (
            contract["end_date"]
            and as_date(contract["end_date"])
            < as_date(contract["start_date"])
        ):
            contract_errors += 1
    add(
        "contract_client_and_date_consistency",
        contract_errors == 0,
        f"{contract_errors} contract inconsistencies",
    )
    add(
        "one_primary_contract_per_client",
        len(contracts)
        == len({row["client_id"] for row in contracts})
        == len(clients),
        f"{len(contracts)} contracts for {len(clients)} clients",
    )

    add(
        "contract_service_fk",
        all(
            row["contract_id"] in contract_by_id
            for row in contract_services
        ),
        "contract service → contract",
    )
    add(
        "contract_service_type_fk",
        all(
            row["service_type_code"] in service_type_ids
            for row in contract_services
        ),
        "contract service → service type",
    )

    add(
        "bank_account_client_fk",
        all(row["client_id"] in client_by_id for row in bank_accounts),
        "bank account → client",
    )
    add(
        "bank_account_currency_fk",
        all(row["currency_code"] in currency_ids for row in bank_accounts),
        "bank account → currency",
    )
    add(
        "counterparty_client_fk",
        all(row["client_id"] in client_by_id for row in counterparties),
        "counterparty → client",
    )
    add(
        "counterparty_currency_fk",
        all(row["currency_code"] in currency_ids for row in counterparties),
        "counterparty → currency",
    )

    # Large transaction tables are streamed rather than loaded as lists.
    document_ids: set[str] = set()
    document_meta: dict[str, tuple[str, str]] = {}
    document_reference_first: dict[tuple[str, str], str] = {}
    duplicate_reference_errors = 0
    document_pk_errors = 0
    document_fk_errors = 0
    document_count = 0

    for row in iter_csv(input_dir, "accounting_document"):
        document_count += 1
        document_id = row["document_id"]
        if document_id in document_ids:
            document_pk_errors += 1
        document_ids.add(document_id)

        if (
            row["client_id"] not in client_by_id
            or row["document_type_code"] not in document_type_ids
        ):
            document_fk_errors += 1

        key = (row["client_id"], row["external_reference"])
        prior = document_reference_first.get(key)
        if prior is None:
            document_reference_first[key] = document_id
        elif not (
            expected(
                "accounting_document",
                document_id,
                "DUPLICATE_DOCUMENT_REFERENCE",
            )
            or expected(
                "accounting_document",
                prior,
                "DUPLICATE_DOCUMENT_REFERENCE",
            )
        ):
            duplicate_reference_errors += 1

        document_meta[document_id] = (
            row["client_id"],
            row["external_reference"],
        )

    add(
        "accounting_document_nonempty",
        document_count > 0,
        f"{document_count} rows",
    )
    add(
        "accounting_document_primary_key_uniqueness",
        document_pk_errors == 0,
        f"{document_pk_errors} duplicate IDs",
    )
    add(
        "accounting_document_foreign_keys",
        document_fk_errors == 0,
        f"{document_fk_errors} FK errors",
    )
    add(
        "document_reference_uniqueness_or_expected_dq",
        duplicate_reference_errors == 0,
        f"{duplicate_reference_errors} unexplained duplicates",
    )

    invoice_ids: set[str] = set()
    invoice_meta: dict[str, tuple[str, date, date]] = {}
    invoice_pk_errors = 0
    invoice_fk_errors = 0
    invoice_arithmetic_errors = 0
    invoice_date_errors = 0
    unexpected_vat_rate_errors = 0
    invoice_count = 0
    allowed_vat_rates = {
        Decimal("0"),
        Decimal("0.07"),
        Decimal("0.19"),
    }

    for row in iter_csv(input_dir, "business_invoice"):
        invoice_count += 1
        invoice_id = row["invoice_id"]
        if invoice_id in invoice_ids:
            invoice_pk_errors += 1
        invoice_ids.add(invoice_id)

        document = document_meta.get(row["document_id"])
        counterparty = counterparty_by_id.get(row["counterparty_id"])
        if (
            document is None
            or row["client_id"] not in client_by_id
            or counterparty is None
            or document[0] != row["client_id"]
            or counterparty["client_id"] != row["client_id"]
            or row["currency_code"] not in currency_ids
        ):
            invoice_fk_errors += 1

        if document and row["invoice_number"] != document[1]:
            invoice_fk_errors += 1

        net = Decimal(row["net_amount"])
        vat = Decimal(row["vat_amount"])
        gross = Decimal(row["gross_amount"])
        if abs((net + vat) - gross) > Decimal("0.02"):
            invoice_arithmetic_errors += 1

        issue = as_date(row["issue_date"])
        due = as_date(row["due_date"])
        if due < issue:
            invoice_date_errors += 1

        vat_rate = Decimal(row["vat_rate"])
        if (
            vat_rate not in allowed_vat_rates
            and not expected(
                "business_invoice",
                invoice_id,
                "INVALID_VAT_RATE",
            )
        ):
            unexpected_vat_rate_errors += 1

        invoice_meta[invoice_id] = (
            row["client_id"],
            issue,
            due,
        )

    add(
        "business_invoice_nonempty",
        invoice_count > 0,
        f"{invoice_count} rows",
    )
    add(
        "business_invoice_primary_key_uniqueness",
        invoice_pk_errors == 0,
        f"{invoice_pk_errors} duplicate IDs",
    )
    add(
        "invoice_document_client_counterparty_consistency",
        invoice_fk_errors == 0,
        f"{invoice_fk_errors} relationship errors",
    )
    add(
        "invoice_arithmetic",
        invoice_arithmetic_errors == 0,
        f"{invoice_arithmetic_errors} arithmetic errors",
    )
    add(
        "invoice_date_order",
        invoice_date_errors == 0,
        f"{invoice_date_errors} invalid due dates",
    )
    add(
        "invoice_vat_rate_or_expected_dq",
        unexpected_vat_rate_errors == 0,
        f"{unexpected_vat_rate_errors} unexplained invalid VAT rates",
    )

    payment_ids: set[str] = set()
    payment_errors = 0
    payment_count = 0
    for row in iter_csv(input_dir, "payment"):
        payment_count += 1
        if row["payment_id"] in payment_ids:
            payment_errors += 1
        payment_ids.add(row["payment_id"])
        invoice = invoice_meta.get(row["invoice_id"])
        if (
            invoice is None
            or invoice[0] != row["client_id"]
            or row["currency_code"] not in currency_ids
            or as_date(row["payment_date"]) < invoice[1]
        ):
            payment_errors += 1
    add(
        "payment_integrity",
        payment_errors == 0,
        f"{payment_count} rows; {payment_errors} errors",
    )

    bank_transaction_ids: set[str] = set()
    bank_transaction_errors = 0
    bank_transaction_count = 0
    for row in iter_csv(input_dir, "bank_transaction"):
        bank_transaction_count += 1
        transaction_id = row["bank_transaction_id"]
        if transaction_id in bank_transaction_ids:
            bank_transaction_errors += 1
        bank_transaction_ids.add(transaction_id)
        account = bank_account_by_id.get(row["bank_account_id"])
        if (
            account is None
            or account["client_id"] != row["client_id"]
            or row["currency_code"] not in currency_ids
            or as_date(row["value_date"])
            < as_date(row["transaction_date"])
        ):
            bank_transaction_errors += 1
    add(
        "bank_transaction_integrity",
        bank_transaction_errors == 0,
        (
            f"{bank_transaction_count} rows; "
            f"{bank_transaction_errors} errors"
        ),
    )

    match_ids: set[str] = set()
    match_errors = 0
    match_count = 0
    for row in iter_csv(input_dir, "reconciliation_match"):
        match_count += 1
        match_id = row["reconciliation_match_id"]
        if match_id in match_ids:
            match_errors += 1
        match_ids.add(match_id)
        if (
            row["bank_transaction_id"] not in bank_transaction_ids
            or row["invoice_id"] not in invoice_ids
        ):
            match_errors += 1
    add(
        "reconciliation_match_integrity",
        match_errors == 0,
        f"{match_count} rows; {match_errors} errors",
    )

    journal_entry_ids: set[str] = set()
    journal_entry_errors = 0
    journal_entry_count = 0
    for row in iter_csv(input_dir, "journal_entry"):
        journal_entry_count += 1
        entry_id = row["journal_entry_id"]
        if entry_id in journal_entry_ids:
            journal_entry_errors += 1
        journal_entry_ids.add(entry_id)
        if row["client_id"] not in client_by_id:
            journal_entry_errors += 1
        if (
            row["source_document_id"]
            and row["source_document_id"] not in document_ids
        ):
            journal_entry_errors += 1
        if row["currency_code"] not in currency_ids:
            journal_entry_errors += 1
    add(
        "journal_entry_integrity",
        journal_entry_errors == 0,
        (
            f"{journal_entry_count} rows; "
            f"{journal_entry_errors} errors"
        ),
    )

    journal_line_ids: set[str] = set()
    journal_line_errors = 0
    unbalanced_entries = 0
    journal_line_count = 0
    current_entry_id: str | None = None
    current_debit = Decimal("0")
    current_credit = Decimal("0")

    def close_current_entry() -> None:
        nonlocal unbalanced_entries
        if (
            current_entry_id is not None
            and abs(current_debit - current_credit) > Decimal("0.01")
        ):
            unbalanced_entries += 1

    for row in iter_csv(input_dir, "journal_line"):
        journal_line_count += 1
        line_id = row["journal_line_id"]
        if line_id in journal_line_ids:
            journal_line_errors += 1
        journal_line_ids.add(line_id)

        entry_id = row["journal_entry_id"]
        if (
            entry_id not in journal_entry_ids
            or row["gl_account_code"] not in gl_account_ids
        ):
            journal_line_errors += 1

        if current_entry_id is None:
            current_entry_id = entry_id
        elif entry_id != current_entry_id:
            close_current_entry()
            current_entry_id = entry_id
            current_debit = Decimal("0")
            current_credit = Decimal("0")

        current_debit += Decimal(row["debit_amount_eur"])
        current_credit += Decimal(row["credit_amount_eur"])

    close_current_entry()

    add(
        "journal_line_integrity",
        journal_line_errors == 0,
        (
            f"{journal_line_count} rows; "
            f"{journal_line_errors} errors"
        ),
    )
    add(
        "balanced_journal_entries",
        unbalanced_entries == 0,
        f"{unbalanced_entries} unbalanced entries",
    )

    tax_filing_errors = 0
    tax_filing_count = 0
    for row in iter_csv(input_dir, "tax_filing"):
        tax_filing_count += 1
        if row["client_id"] not in client_by_id:
            tax_filing_errors += 1
            continue
        prepared = as_date(row["prepared_date"])
        reviewed = as_date(row["reviewed_date"])
        submitted = as_date(row["submitted_date"])
        if not (prepared <= reviewed <= submitted):
            tax_filing_errors += 1
    add(
        "tax_filing_integrity",
        tax_filing_errors == 0,
        f"{tax_filing_count} rows; {tax_filing_errors} errors",
    )

    document_request_ids: set[str] = set()
    document_request_errors = 0
    document_request_count = 0
    for row in iter_csv(input_dir, "document_request"):
        document_request_count += 1
        request_id = row["document_request_id"]
        if request_id in document_request_ids:
            document_request_errors += 1
        document_request_ids.add(request_id)
        if (
            row["client_id"] not in client_by_id
            or row["accountant_id"] not in employee_by_id
            or as_date(row["due_date"]) < as_date(row["request_date"])
            or (
                row["response_date"]
                and as_date(row["response_date"])
                < as_date(row["request_date"])
            )
        ):
            document_request_errors += 1
    add(
        "document_request_integrity",
        document_request_errors == 0,
        (
            f"{document_request_count} rows; "
            f"{document_request_errors} errors"
        ),
    )

    communication_errors = 0
    communication_count = 0
    for row in iter_csv(input_dir, "communication_event"):
        communication_count += 1
        if (
            row["client_id"] not in client_by_id
            or row["employee_id"] not in employee_by_id
            or (
                row["document_request_id"]
                and row["document_request_id"]
                not in document_request_ids
            )
        ):
            communication_errors += 1
    add(
        "communication_event_integrity",
        communication_errors == 0,
        f"{communication_count} rows; {communication_errors} errors",
    )

    work_item_errors = 0
    work_item_count = 0
    for row in iter_csv(input_dir, "work_item"):
        work_item_count += 1
        created = as_datetime(row["created_timestamp"])
        due = as_datetime(row["due_timestamp"])
        completed = as_datetime(row["completed_timestamp"])
        if (
            row["client_id"] not in client_by_id
            or row["task_type_code"] not in task_type_ids
            or row["assigned_employee_id"] not in employee_by_id
            or not (created <= due)
            or completed < created
        ):
            work_item_errors += 1
    add(
        "work_item_integrity",
        work_item_errors == 0,
        f"{work_item_count} rows; {work_item_errors} errors",
    )

    firm_invoice_ids: set[str] = set()
    firm_invoice_errors = 0
    firm_invoice_count = 0
    for row in iter_csv(input_dir, "firm_invoice"):
        firm_invoice_count += 1
        invoice_id = row["firm_invoice_id"]
        if invoice_id in firm_invoice_ids:
            firm_invoice_errors += 1
        firm_invoice_ids.add(invoice_id)
        client = client_by_id.get(row["client_id"])
        contract = contract_by_id.get(row["contract_id"])
        if (
            client is None
            or contract is None
            or row["firm_id"] != client["firm_id"]
            or contract["client_id"] != row["client_id"]
            or as_date(row["due_date"]) < as_date(row["issue_date"])
        ):
            firm_invoice_errors += 1
    add(
        "firm_invoice_integrity",
        firm_invoice_errors == 0,
        f"{firm_invoice_count} rows; {firm_invoice_errors} errors",
    )

    firm_payment_errors = 0
    firm_payment_count = 0
    for row in iter_csv(input_dir, "firm_payment"):
        firm_payment_count += 1
        if row["firm_invoice_id"] not in firm_invoice_ids:
            firm_payment_errors += 1
    add(
        "firm_payment_integrity",
        firm_payment_errors == 0,
        f"{firm_payment_count} rows; {firm_payment_errors} errors",
    )

    report = {
        "input_directory": str(input_dir),
        "passed": all(
            check["passed"]
            or check["failure_severity"] != "ERROR"
            for check in checks
        ),
        "failed_check_count": sum(
            not check["passed"]
            and check["failure_severity"] == "ERROR"
            for check in checks
        ),
        "warning_count": sum(
            not check["passed"]
            and check["failure_severity"] == "WARNING"
            for check in checks
        ),
        "expected_dq_issue_count": len(expected_issues),
        "checks": checks,
    }
    (input_dir / "validation_report.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    return report
