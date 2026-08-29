# Architecture

The generator models three separate domains:

1. accounting-practice organisation;
2. client-company accounting;
3. service relationship and workflow.

This prevents the accounting firm's own revenue from being mixed with the
client company's sales, costs and balances.

The output is normalized. Dashboard aggregates are intentionally not
generated here; they belong in the future SQL analytics repository.

Version 1 intentionally excludes employee promotions, absences, dismissals,
temporary employment, full statutory charts of accounts, group consolidation
and detailed FX revaluation accounting.
