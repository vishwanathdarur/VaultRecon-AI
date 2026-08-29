# Changelog

## 2.3.0

- changed the default and portfolio history to 36 complete months,
  covering 2023–2025;
- guaranteed at least one example of every supported DQ rule in the
  default, development and portfolio configurations;
- preserved probability-based generation for additional DQ issues;
- added regression coverage for guaranteed DQ minimums.

## 2.2.0

- corrected VAT registration and VAT ID consistency;
- guaranteed unique client-company names;
- guaranteed unique employee and client-contact email addresses;
- enforced firm, office, employment, incorporation, onboarding and
  termination date order;
- added legal-form consistency checks for company names;
- added role and same-firm assignment validation;
- added reference-table and transactional foreign-key validation;
- added expected-DQ-aware validation;
- changed the validation field from `severity` to `failure_severity`;
- converted large-table validation to streaming checks where practical;
- added generation progress output;
- reduced the safe default dataset to approximately 1,960–2,990 clients;
- moved the previous extreme scale to `config/profiles/full.yaml`;
- added regression tests for business rules and expected DQ defects.

## 2.1.0

- established shared Synthetic Accounting Analytics Platform conventions;
- standardised README structure and MIT licence;
- added representative sample data.

## 2.0.0

- introduced YAML configuration, scale profiles, business scenarios and
  dotted CLI overrides.
