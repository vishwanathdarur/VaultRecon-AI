$ErrorActionPreference = "Stop"
python -m synthetic_accounting_generator.cli generate `
  --config config/config.yaml `
  --profile config/profiles/portfolio.yaml `
  --scenario config/scenarios/baseline.yaml `
  --output data/generated/portfolio
