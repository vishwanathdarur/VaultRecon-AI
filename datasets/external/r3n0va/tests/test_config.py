from pathlib import Path

from synthetic_accounting_generator.config import load_effective_config


def test_dotted_override_changes_counts() -> None:
    root = Path(__file__).resolve().parents[1]
    config = load_effective_config(
        root / "config/config.yaml",
        root / "config/profiles/smoke.yaml",
        root / "config/scenarios/baseline.yaml",
        [
            "firms.small.count=2",
            "firms.small.clients.min=11",
            "firms.small.clients.max=11",
            "runtime.progress=false",
        ],
    )
    assert config["firms"]["small"]["count"] == 2
    assert config["firms"]["small"]["clients"]["min"] == 11
    assert config["firms"]["small"]["clients"]["max"] == 11
    assert config["runtime"]["progress"] is False


def test_default_scale_is_portfolio_safe() -> None:
    root = Path(__file__).resolve().parents[1]
    config = load_effective_config(root / "config/config.yaml")

    minimum_clients = sum(
        int(config["firms"][size]["count"])
        * int(config["firms"][size]["clients"]["min"])
        for size in ("small", "medium", "large")
    )
    maximum_clients = sum(
        int(config["firms"][size]["count"])
        * int(config["firms"][size]["clients"]["max"])
        for size in ("small", "medium", "large")
    )

    assert config["project"]["months"] == 36
    assert minimum_clients == 1960
    assert maximum_clients == 2990
