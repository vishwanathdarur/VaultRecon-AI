# Synthetic Accounting Data Generator

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![Tests](https://img.shields.io/badge/tests-passing-brightgreen)
![Data](https://img.shields.io/badge/data-fully%20synthetic-orange)
![Status](https://img.shields.io/badge/status-active-success)
![Purpose](https://img.shields.io/badge/purpose-portfolio-lightgrey)

A configurable Python application for generating a fully synthetic,
deterministic and internally consistent relational accounting dataset.

The generator models German accounting practices, their offices and employees,
the legal entities they serve, client accounting activity, service workflows,
communications and accounting-practice billing.

This repository contains the data-generation layer of the broader
**Synthetic Accounting Analytics Platform**.

---

## Platform Structure

The platform is organised as five separate GitHub repositories:

```text
01  Synthetic Accounting Data Generator
              │
              ▼
02  Synthetic Accounting SQL
              │
              ▼
03  Synthetic Accounting Analytics
              │
              ▼
04  Synthetic Accounting Data Quality
              │
              ▼
05  Synthetic Accounting A/B Testing
```

Corresponding repository names:

- [Synthetic Accounting Data Generator](https://github.com/R3n0va/synthetic-accounting-data-generator)
- [Synthetic Accounting SQL](https://github.com/R3n0va/synthetic-accounting-sql)
- [Synthetic Accounting Analytics](https://github.com/R3n0va/synthetic-accounting-analytics)
- [Synthetic Accounting Data Quality](https://github.com/R3n0va/synthetic-accounting-data-quality)
- [Synthetic Accounting A/B Testing](https://github.com/R3n0va/synthetic-accounting-ab-testing)

All five are standalone repositories. The numbering defines their order within
the portfolio and provides a clear path through the platform. It does not mean
that one repository is physically contained inside another.

This repository is responsible only for the first layer: generating the
synthetic source dataset used by the later repositories.

---

## Project Overview

```text
Master Configuration
        │
        ├── Scale Profile
        ├── Business Scenario
        └── CLI Overrides
        │
        ▼
Synthetic Accounting Data Generator
        │
        ▼
Normalised Relational CSV Dataset
        │
        ├── Generation Manifest
        ├── Effective Configuration
        ├── DQ Issue Manifest
        └── Validation Report
```

The generated files can then be used independently by the SQL, analytics,
data-quality and A/B-testing repositories.

---

## Key Features

- fully synthetic accounting data;
- configuration-driven generation;
- separate scale profiles and business scenarios;
- command-line overrides without editing Python;
- deterministic output based on a random seed;
- stable primary keys;
- referential consistency between generated entities;
- normalised relational source tables;
- real German federal states and cities;
- German legal forms;
- configurable firm, office, employee and client volumes;
- client-company accounting activity;
- accounts receivable and accounts payable;
- bank transactions and reconciliation;
- balanced double-entry journal entries;
- VAT filing workflows;
- accountant tasks and client communications;
- accounting-practice billing;
- controlled data-quality issue injection;
- guaranteed minimum DQ coverage in working profiles;
- automatic post-generation validation;
- expected-DQ-aware validation;
- streaming validation for large transactional tables;
- unique company names and email addresses at scale;
- explicit lifecycle and employment date consistency;
- visible progress during longer generation runs;
- representative validated sample dataset;
- automated tests and GitHub Actions workflow.

---

## Accounting Domain

The project represents accounting firms that manage bookkeeping and related
services for German legal entities.

### Accounting practices

The default configuration contains:

| Size class | Firms | Offices per firm | Employees per firm | Clients per firm |
|---|---:|---:|---:|---:|
| Small | 4 | 1 | 5–10 | 100–160 |
| Medium | 3 | 2–3 | 16–30 | 220–350 |
| Large | 2 | 5–7 | 38–60 | 450–650 |

Generated employee roles are limited to:

- Head;
- Junior Client Manager;
- Senior Client Manager;
- Junior Accountant;
- Senior Accountant.

All generated employment contracts are permanent.

The default working configuration produces approximately **1,960–2,990
client companies over 36 complete months**, covering **2023–2025**.

### Client companies

Client companies range from one-person owner-managed entities and low-activity
holdings to manufacturers, logistics businesses, port-related companies and
organisations with up to 1,000 employees.

The model includes:

- German legal form;
- industry;
- real German city and federal state;
- employee count;
- estimated annual revenue;
- transaction-volume band;
- VAT registration;
- accounting complexity;
- risk category;
- digital maturity;
- preferred communication channel;
- lifecycle status;
- foreign-trade flag.

### Accounting services

The generated service catalogue includes:

- financial accounting;
- accounts payable;
- accounts receivable;
- VAT returns;
- payroll;
- management reporting;
- annual financial statements;
- corporate tax;
- advisory;
- company formation;
- company closure.

Pricing can depend on:

- company size;
- transaction volume;
- employee count;
- accounting complexity;
- selected services;
- service-level requirements.

---

## Generated Dataset

### Reference data

| Output file | Description |
|---|---|
| `region.csv` | German federal states |
| `city.csv` | Real German cities and coordinates |
| `legal_form.csv` | Supported German legal forms |
| `industry.csv` | Client industry classification |
| `currency.csv` | Supported currencies |
| `service_type.csv` | Accounting service catalogue |
| `document_type.csv` | Primary-document types |
| `task_type.csv` | Accountant task types |
| `gl_account.csv` | Controlled ledger-account subset |
| `fx_rate.csv` | Synthetic monthly EUR conversion rates |

### Accounting-practice organisation

| Output file | Description |
|---|---|
| `accounting_firm.csv` | Accounting practices |
| `office.csv` | Practice offices |
| `employee.csv` | Permanent employees |

### Client relationship

| Output file | Description |
|---|---|
| `client_company.csv` | Served legal entities |
| `client_contact.csv` | Primary client contacts |
| `client_assignment.csv` | Assigned client manager and accountant |
| `client_event.csv` | Onboarding and lifecycle events |

### Contracts and services

| Output file | Description |
|---|---|
| `service_contract.csv` | Principal client contracts |
| `contract_service.csv` | Services included in each contract |

### Client accounting

| Output file | Description |
|---|---|
| `bank_account.csv` | Client bank accounts |
| `counterparty.csv` | Client customers and suppliers |
| `accounting_document.csv` | Primary documents and ingestion metadata |
| `business_invoice.csv` | Accounts receivable and payable invoices |
| `payment.csv` | Invoice payments |
| `bank_transaction.csv` | Client bank movements |
| `reconciliation_match.csv` | Invoice-to-bank matches |
| `journal_entry.csv` | Journal headers |
| `journal_line.csv` | Debit and credit lines |
| `tax_filing.csv` | VAT filing instances |

### Workflow and communication

| Output file | Description |
|---|---|
| `document_request.csv` | Missing-document requests |
| `communication_event.csv` | Client and practice interactions |
| `work_item.csv` | Accountant tasks and effort |

### Accounting-practice billing

| Output file | Description |
|---|---|
| `firm_invoice.csv` | Charges issued by the accounting practice |
| `firm_payment.csv` | Client payments of practice invoices |

### Quality and metadata

| Output file | Description |
|---|---|
| `dq_issue_manifest.csv` | Intentionally injected defects |
| `generation_manifest.json` | Effective generation summary |
| `effective_config.yaml` | Fully merged configuration |
| `validation_report.json` | Machine-readable validation results |

---

## Validated Default Run

The default configuration was executed locally with seed `2026` for the full
period from `2023-01-01` to `2025-12-31`.

The completed run produced:

| Entity | Rows |
|---|---:|
| Accounting firms | 9 |
| Offices | 24 |
| Employees | 210 |
| Client companies | 2,371 |
| Client assignments | 2,371 |
| Service contracts | 2,371 |
| Accounting documents | 1,354,099 |
| Business invoices | 1,354,099 |
| Payments | 1,137,188 |
| Bank transactions | 1,137,188 |
| Reconciliation matches | 1,137,188 |
| Journal entries | 2,491,287 |
| Journal lines | 6,336,673 |
| Work items | 269,400 |
| Tax filings | 57,073 |
| Document requests | 58,493 |
| Communication events | 175,479 |
| Accounting-practice invoices | 68,593 |
| Accounting-practice payments | 63,672 |
| Expected DQ issues | 2,662 |

The automatic validation and the separate validation command both completed
successfully:

```json
{
  "passed": true,
  "failed_check_count": 0,
  "warning_count": 0,
  "expected_dq_issue_count": 2662
}
```

---

## Sample Dataset

A small validated sample is included in:

```text
data/samples/
```

It allows reviewers to inspect representative tables and relationships without
running the complete generator.

Complete generated datasets are written to:

```text
data/generated/
```

The complete-output directory is excluded from Git.

---

## Data Relationships

Examples of enforced relationships include:

- every office belongs to an existing accounting firm;
- every employee belongs to an existing firm and office;
- every employee office belongs to the same firm as the employee;
- every client belongs to an existing accounting firm;
- every client primary office belongs to the same accounting firm;
- every client has one current client-manager/accountant assignment;
- every assignment uses the correct employee roles;
- every contract belongs to an existing client;
- every contract service belongs to an existing contract;
- every invoice belongs to an accounting document and counterparty;
- every payment references an existing invoice;
- every bank transaction references an existing bank account;
- every reconciliation match references an invoice and bank transaction;
- every journal line belongs to an existing journal entry;
- every generated journal entry balances;
- accounting-practice invoices are kept separate from client-company invoices.

---

## Generation Pipeline

```text
Reference Data
      │
      ▼
Accounting Firms
      │
      ▼
Offices and Employees
      │
      ▼
Client Companies
      │
      ▼
Assignments and Contracts
      │
      ▼
Services, Accounts and Counterparties
      │
      ▼
Documents and Business Invoices
      │
      ▼
Payments and Bank Reconciliation
      │
      ▼
Journal Entries and Tax Filings
      │
      ▼
Tasks, Requests and Communications
      │
      ▼
Accounting-Practice Billing
      │
      ▼
Data-Quality Manifest
      │
      ▼
Dataset Validation
```

Generation stages use configuration values and entities created by earlier
stages.

---

## Project Structure

```text
synthetic-accounting-data-generator/
│
├── config/
│   ├── config.yaml
│   ├── profiles/
│   │   ├── smoke.yaml
│   │   ├── dev.yaml
│   │   ├── portfolio.yaml
│   │   └── full.yaml
│   └── scenarios/
│       ├── baseline.yaml
│       ├── growth.yaml
│       ├── stress.yaml
│       └── digital.yaml
│
├── data/
│   ├── generated/
│   ├── output/
│   └── samples/
│
├── docs/
│   ├── 00_PROJECT_CONVENTIONS.md
│   ├── 01_ARCHITECTURE.md
│   ├── 02_CONFIGURATION.md
│   ├── 03_DATA_MODEL.md
│   ├── 04_GENERATION_RULES.md
│   ├── 05_DATA_DICTIONARY.md
│   └── 06_ANALYTICAL_USE_CASES.md
│
├── scripts/
├── src/
│   └── synthetic_accounting_generator/
├── tests/
├── .github/
│   └── workflows/
├── .gitignore
├── CHANGELOG.md
├── LICENSE
├── pyproject.toml
├── README.md
└── requirements.txt
```

---

## Configuration

The master configuration is:

```text
config/config.yaml
```

Configuration is merged in this order:

```text
Master Configuration
        │
        ▼
Optional Profile
        │
        ▼
Optional Scenario
        │
        ▼
CLI Overrides
        │
        ▼
Effective Configuration
```

Later layers override earlier layers.

### Profiles

- `smoke.yaml` — minimal clean dataset for automated and local verification;
- `dev.yaml` — development-sized dataset;
- `portfolio.yaml` — explicit 36-month portfolio dataset;
- `full.yaml` — maximum-scale stress configuration.

### Scenarios

- `baseline.yaml` — stable operating environment;
- `growth.yaml` — accelerated client growth and workload;
- `stress.yaml` — late documents, payment delays and operational pressure;
- `digital.yaml` — increased digital document exchange and automation.

Scenarios change causal multipliers without creating a separate data model.

### Exact counts

Exactly 400 clients in every small firm:

```bash
accounting-data-generator generate \
  --config config/config.yaml \
  --set firms.small.clients.min=400 \
  --set firms.small.clients.max=400 \
  --output data/generated/custom
```

Five small firms:

```bash
accounting-data-generator generate \
  --config config/config.yaml \
  --set firms.small.count=5 \
  --output data/generated/custom
```

Disable progress output:

```bash
accounting-data-generator generate \
  --config config/config.yaml \
  --set runtime.progress=false \
  --output data/generated/custom
```

---

## Deterministic Generation

The same effective configuration and random seed produce the same synthetic
population and relationships.

```yaml
project:
  seed: 2026
```

Changing the seed produces another synthetic dataset while preserving the
configured structure and business rules.

---

## Data-Quality Injection

The working configurations support three controlled DQ rules:

- `MISSING_VAT_ID`;
- `INVALID_VAT_RATE`;
- `DUPLICATE_DOCUMENT_REFERENCE`.

The default, development and portfolio configurations guarantee at least one
example of every supported rule. Additional issues are created according to
configured probabilities.

All intentionally injected issues are recorded in:

```text
dq_issue_manifest.csv
```

The validator distinguishes expected injected defects from unexplained
business-rule violations.

The smoke profile remains clean.

---

## Installation

### 1. Create a virtual environment

Windows:

```cmd
py -3.14 -m venv .venv
.venv\Scripts\activate
```

### 2. Install the project and development dependencies

```cmd
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### 3. Select the interpreter in VS Code

```text
Python: Select Interpreter
→ .venv\Scripts\python.exe
```

---

## Usage

### Smoke generation

```cmd
accounting-data-generator generate --config config/config.yaml --profile config/profiles/smoke.yaml --scenario config/scenarios/baseline.yaml --output data/generated/smoke
```

### Development generation

```cmd
accounting-data-generator generate --config config/config.yaml --profile config/profiles/dev.yaml --scenario config/scenarios/baseline.yaml --output data/generated/dev
```

### Portfolio generation

```cmd
accounting-data-generator generate --config config/config.yaml --profile config/profiles/portfolio.yaml --scenario config/scenarios/baseline.yaml --output data/generated/portfolio
```

### Default working generation

```cmd
accounting-data-generator generate --config config/config.yaml --scenario config/scenarios/baseline.yaml --output data/generated/default
```

The default command generates the 36-month 2023–2025 working dataset.

### Full stress generation

```cmd
accounting-data-generator generate --config config/config.yaml --profile config/profiles/full.yaml --scenario config/scenarios/baseline.yaml --output data/generated/full
```

The full profile can create substantially larger outputs and is intended for
stress and performance testing.

### Display the merged configuration

```cmd
accounting-data-generator show-config --config config/config.yaml --profile config/profiles/portfolio.yaml --scenario config/scenarios/baseline.yaml
```

---

## Validation

Run automated tests:

```cmd
pytest
```

Validate an existing dataset:

```cmd
accounting-data-generator validate --input data/generated/default
```

Validation checks include:

- required table presence;
- primary-key uniqueness;
- reference and transactional foreign-key consistency;
- unique client-company names;
- unique employee and client-contact email addresses;
- VAT registration and VAT ID consistency;
- legal-form consistency in company names;
- firm, office, employment and client-lifecycle date ordering;
- role-correct and same-firm client assignments;
- assignment and contract uniqueness;
- document-reference uniqueness or documented DQ exceptions;
- allowed VAT rates or documented DQ exceptions;
- invoice arithmetic;
- payment integrity;
- bank-transaction integrity;
- reconciliation integrity;
- balanced journal entries;
- filing integrity;
- workflow and communication integrity;
- accounting-practice billing integrity.

Successful validation produces:

```text
validation_report.json
```

with:

```json
{
  "passed": true,
  "failed_check_count": 0
}
```

---

## Design Principles

- configuration-driven behaviour;
- deterministic generation;
- reproducible output;
- stable identifiers;
- normalised relational source tables;
- explicit generation dependencies;
- valid cross-table references;
- realistic business causality;
- separation of client accounting and accounting-practice billing;
- separation of generation and validation;
- controlled data-quality defects;
- no dependency on real client data;
- explicit scope boundaries;
- separate downstream repositories.

---

## Repository Scope

This repository is responsible only for:

- configuration processing;
- synthetic entity generation;
- synthetic accounting activity;
- controlled DQ injection;
- CSV output;
- generation metadata;
- post-generation validation.

It does not contain:

- PostgreSQL schema implementation;
- SQL transformations;
- analytical models;
- standalone data-quality framework;
- statistical experiment analysis.

Those areas belong to the other standalone repositories in the platform:

```text
01  synthetic-accounting-data-generator
02  synthetic-accounting-sql
03  synthetic-accounting-analytics
04  synthetic-accounting-data-quality
05  synthetic-accounting-ab-testing
```

A downstream repository is published only after its own layer is implemented
and validated.

---

## Intended Use

Generated data can support:

- PostgreSQL data modelling;
- ETL development;
- SQL analytics;
- operational accounting analytics;
- client-portfolio analysis;
- regional analysis;
- revenue and service analysis;
- accountant workload analysis;
- accounts-receivable and accounts-payable analysis;
- bank-reconciliation analysis;
- data-quality controls;
- statistical experiments;
- portfolio demonstrations.

---

## Documentation

Project documentation is stored in:

```text
docs/
```

It includes:

- shared platform conventions;
- architecture;
- configuration;
- logical data model;
- generation rules;
- data dictionary;
- analytical use cases.

---

## Data Privacy

The project does not use, transform or reproduce real accounting-firm or
client-company data.

All firms, offices, employees, contacts, legal entities, documents, invoices,
payments, bank transactions, journal entries, communications and results are
programmatically generated.

Any resemblance to real people, organisations, accounts, documents or
transactions is coincidental.

---

## Status

The current version is **2.3.0**.

Implemented and validated:

- YAML-driven generation;
- profiles and scenarios;
- CLI overrides;
- German reference data;
- accounting-practice organisation;
- client relationship modelling;
- contracts and services;
- primary documents;
- accounts-receivable and accounts-payable invoices;
- payments and bank reconciliation;
- balanced journals;
- VAT filings;
- workflow and communication;
- accounting-practice billing;
- controlled DQ injection;
- automated tests;
- machine-readable validation;
- representative sample data;
- completed default-scale generation;
- completed separate validation of the default dataset.

---

## License

This project is released under the MIT License.

See [LICENSE](LICENSE) for the complete license text.
