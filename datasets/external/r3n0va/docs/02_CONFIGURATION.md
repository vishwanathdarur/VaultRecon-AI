# Configuration

## Merge order

The effective configuration is merged in this order:

1. `config/config.yaml`;
2. optional profile;
3. optional scenario;
4. CLI `--set` overrides.

Later layers win.

## Default working scale

The master configuration is deliberately safe for a local 16 GB development
machine:

- 9 accounting firms;
- approximately 1,960–2,990 clients;
- 36 months (2023–2025);
- reduced document-volume ranges;
- visible progress every 100 clients.

## Exact counts

Exactly 300 clients in every small firm:

```bash
--set firms.small.clients.min=300
--set firms.small.clients.max=300
```

Disable large firms:

```bash
--set firms.large.count=0
```

Disable progress output:

```bash
--set runtime.progress=false
```

## Profiles

- `smoke.yaml` — automated and local verification;
- `dev.yaml` — small development dataset;
- `portfolio.yaml` — explicit portfolio working scale;
- `full.yaml` — former maximum-scale stress configuration.

## Scenarios

- `baseline.yaml`;
- `growth.yaml`;
- `stress.yaml`;
- `digital.yaml`.

Scenarios change causal multipliers instead of creating a parallel data model.


## Minimum DQ coverage

The default, `dev` and `portfolio` configurations guarantee at least one
generated example of:

- `MISSING_VAT_ID`;
- `INVALID_VAT_RATE`;
- `DUPLICATE_DOCUMENT_REFERENCE`.

Probabilities still control additional issues. The minimum only ensures
that every supported rule is represented in the generated dataset.
