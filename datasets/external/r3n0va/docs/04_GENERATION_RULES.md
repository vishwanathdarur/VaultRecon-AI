# Generation rules

## Safe default scale

| Class | Count | Offices | Employees | Clients |
|---|---:|---:|---:|---:|
| Small | 4 | 1 | 5–10 | 100–160 |
| Medium | 3 | 2–3 | 16–30 | 220–350 |
| Large | 2 | 5–7 | 38–60 | 450–650 |

The default configuration generates approximately 1,960–2,990 clients over
36 months. This is the normal local-development and portfolio scale.

The previous maximum configuration is available only through:

```text
config/profiles/full.yaml
```

It may create many millions of rows and is intended for stress testing.

## Employees

Only the agreed roles are generated:

- Head;
- Junior Client Manager;
- Senior Client Manager;
- Junior Accountant;
- Senior Accountant.

Every employment contract is permanent. Employment start dates cannot precede
the accounting firm's founding date. Employee email addresses are unique.

## Client companies

Client companies range from one-person owner-managed entities and
low-activity holdings to manufacturers, logistics businesses, port-related
companies and companies with up to 1,000 employees.

Business invariants include:

- every client-company name is unique;
- the company-name suffix matches the legal form;
- incorporation cannot occur after onboarding;
- termination cannot occur before onboarding;
- non-VAT-registered clients have no VAT ID;
- VAT IDs are unique when present;
- client-contact email addresses are unique.

## Causal relationships

Late documents can create:

- document requests;
- automated reminders;
- blocked work items;
- late month-end completion;
- late tax filing;
- higher actual effort.

Client complexity affects:

- service mix;
- tariff;
- document volume;
- work effort.

Digital maturity influences document delivery and communication channels.

## Foreign currency

Germany and EUR remain the base. A subset of clients can have foreign
counterparties and non-EUR accounts. EUR-equivalent values are stored for
analytics. Full realised and unrealised FX accounting is outside this version.

## Data quality

Intentional defects are written to `dq_issue_manifest.csv`. The default, `dev` and `portfolio` configurations guarantee at least one example of each supported DQ rule. Validation
distinguishes expected injected defects from unexplained business-rule
violations.
