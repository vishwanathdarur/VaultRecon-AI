import csv
from pathlib import Path

from synthetic_accounting_generator.config import load_effective_config
from synthetic_accounting_generator.generator import AccountingDatasetGenerator
from synthetic_accounting_generator.validators import validate_dataset


def read_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_smoke_generation_and_business_rules(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    config = load_effective_config(
        root / "config/config.yaml",
        root / "config/profiles/smoke.yaml",
        root / "config/scenarios/baseline.yaml",
        ["runtime.progress=false"],
    )
    output = tmp_path / "dataset"
    manifest = AccountingDatasetGenerator(config, output).generate()
    report = validate_dataset(output)

    clients = read_rows(output / "client_company.csv")
    employees = read_rows(output / "employee.csv")
    contacts = read_rows(output / "client_contact.csv")

    assert manifest["generator_version"] == "2.3.0"
    assert manifest["row_counts"]["accounting_firm"] == 1
    assert manifest["row_counts"]["client_company"] == 8
    assert report["passed"] is True
    assert report["failed_check_count"] == 0

    assert len({row["company_name"] for row in clients}) == len(clients)
    assert len({row["email"] for row in employees}) == len(employees)
    assert len({row["email"] for row in contacts}) == len(contacts)

    assert all(
        row["vat_id"] == ""
        for row in clients
        if row["vat_registered"] == "False"
    )


def test_expected_data_quality_issues_do_not_break_validation(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[1]
    config = load_effective_config(
        root / "config/config.yaml",
        root / "config/profiles/smoke.yaml",
        root / "config/scenarios/baseline.yaml",
        [
            "runtime.progress=false",
            "data_quality.mode=quality-test",
            "data_quality.injection.missing_vat_id_probability=1.0",
            "data_quality.injection.invalid_vat_rate_probability=1.0",
            "data_quality.injection.duplicate_document_reference_probability=1.0",
        ],
    )
    output = tmp_path / "quality_dataset"
    AccountingDatasetGenerator(config, output).generate()
    report = validate_dataset(output)

    assert report["passed"] is True
    assert report["failed_check_count"] == 0
    assert report["expected_dq_issue_count"] > 0


def test_minimum_dq_coverage_is_guaranteed(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    config = load_effective_config(
        root / "config/config.yaml",
        root / "config/profiles/smoke.yaml",
        root / "config/scenarios/baseline.yaml",
        [
            "runtime.progress=false",
            "data_quality.mode=quality-test",
            "data_quality.minimum_issues_per_rule.MISSING_VAT_ID=1",
            "data_quality.minimum_issues_per_rule.INVALID_VAT_RATE=1",
            "data_quality.minimum_issues_per_rule.DUPLICATE_DOCUMENT_REFERENCE=1",
            "data_quality.injection.missing_vat_id_probability=0.0",
            "data_quality.injection.invalid_vat_rate_probability=0.0",
            "data_quality.injection.duplicate_document_reference_probability=0.0",
        ],
    )
    output = tmp_path / "minimum_dq_dataset"
    AccountingDatasetGenerator(config, output).generate()
    report = validate_dataset(output)
    issues = read_rows(output / "dq_issue_manifest.csv")

    counts: dict[str, int] = {}
    for issue in issues:
        counts[issue["rule_code"]] = counts.get(issue["rule_code"], 0) + 1

    assert report["passed"] is True
    assert report["failed_check_count"] == 0
    assert counts["MISSING_VAT_ID"] >= 1
    assert counts["INVALID_VAT_RATE"] >= 1
    assert counts["DUPLICATE_DOCUMENT_REFERENCE"] >= 1
