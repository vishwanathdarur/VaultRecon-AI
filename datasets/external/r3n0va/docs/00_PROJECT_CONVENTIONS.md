# Synthetic Accounting Analytics Platform — Project Conventions

This document defines the shared presentation and repository conventions for
the complete Synthetic Accounting Analytics Platform.

The repositories do not need to copy the older Synthetic Banking project.
They must, however, read as parts of one coherent accounting portfolio created
by the same author.

## Platform name

Use the following platform name in repository descriptions and documentation:

> **Synthetic Accounting Analytics Platform**

## Repository sequence

```text
01  synthetic-accounting-data-generator
02  synthetic-accounting-sql
03  synthetic-accounting-analytics
04  synthetic-accounting-data-quality
05  synthetic-accounting-ab-testing
06  synthetic-accounting-tableau
```

A repository is created only when its layer is genuinely implemented. The
sequence reserves stable names without claiming that unfinished layers exist.

## Repository role statement

Every README must state clearly that the repository contains only one layer of
the broader platform.

Example:

> This repository contains only the synthetic data generation component of the
> broader Synthetic Accounting Analytics Platform.

## README order

All accounting repositories use the same high-level order:

1. title and badges;
2. short purpose statement;
3. project overview;
4. key features;
5. domain or analytical scope;
6. repository-specific outputs;
7. relationships or workflow;
8. project structure;
9. installation and execution;
10. validation;
11. design principles;
12. repository scope;
13. intended use;
14. documentation;
15. data privacy;
16. status;
17. license.

Sections that do not apply may be omitted, but the order of retained sections
must remain stable.

## Documentation

- Documentation is stored in `docs/`.
- Shared conventions are always `00_PROJECT_CONVENTIONS.md`.
- Other documents use two-digit numeric prefixes.
- File names use uppercase snake case.
- Documentation is written in English.
- Claims must describe implemented functionality only.
- Limitations and exclusions must be explicit.

## Code and SQL style

- Python modules use lowercase snake case.
- SQL folders and files use ordered numeric prefixes.
- Stable technical identifiers use English.
- Business terminology is kept consistent across repositories.
- Generated source data, SQL models and analytical outputs remain separate.
- No repository silently creates a parallel version of an upstream model.

## Repository structure

Use the following names where relevant:

```text
config/
data/
docs/
scripts/
src/ or sql/
tests/
.github/workflows/
```

Generated complete datasets are excluded from Git. Small representative
samples may be committed under `data/samples/`.

## Validation evidence

Every repository must expose:

- a reproducible execution command;
- automated or SQL validation;
- a machine-readable result where practical;
- no claim of successful execution without evidence.

## Data privacy wording

Every README must state that all people, companies, documents, transactions
and results are synthetic and that no real client information is used.

## License

Every repository in the accounting platform uses the same complete MIT
License file:

```text
Copyright (c) 2026 R3n0va
```

The README license section must reference the repository `LICENSE` file.

## Visual identity

Use the same badge order:

1. primary technology;
2. validation or tests;
3. synthetic-data status;
4. repository status;
5. portfolio purpose.

Use concise diagrams with the same vertical pipeline style. Avoid decorative
graphics that do not explain architecture, lineage or workflow.

## Evolution from the banking project

The accounting platform may show improved configuration, modelling and
documentation practices. Consistency means shared authorship and design
discipline, not mechanical duplication of the older project.
