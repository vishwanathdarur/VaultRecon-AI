from pathlib import Path

from synthetic_accounting_generator.config import load_effective_config
from synthetic_accounting_generator.generator import AccountingDatasetGenerator
from synthetic_accounting_generator.utils import LEGAL_NAME_SUFFIXES


def test_company_name_generation_scales_to_full_population(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[1]
    config = load_effective_config(
        root / "config/config.yaml",
        overrides=["runtime.progress=false"],
    )
    generator = AccountingDatasetGenerator(config, tmp_path / "unused")

    legal_forms = list(LEGAL_NAME_SUFFIXES)
    names = []
    for index in range(20_000):
        legal_form = legal_forms[index % len(legal_forms)]
        name = generator.unique_client_company_name(
            legal_form,
            "BER",
        )
        names.append(name)
        suffix = LEGAL_NAME_SUFFIXES[legal_form]
        if suffix:
            assert name.endswith(suffix)

    generator.writer.close()
    assert len(names) == len(set(names))
