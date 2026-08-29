from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    if not path.exists():
        raise FileNotFoundError(path)
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def apply_dotted_override(config: dict[str, Any], expression: str) -> None:
    if "=" not in expression:
        raise ValueError(f"Override must use key=value syntax: {expression}")
    dotted_key, raw_value = expression.split("=", 1)
    keys = dotted_key.split(".")
    cursor = config
    for key in keys[:-1]:
        if key not in cursor or not isinstance(cursor[key], dict):
            cursor[key] = {}
        cursor = cursor[key]
    cursor[keys[-1]] = yaml.safe_load(raw_value)


def validate_config(config: dict[str, Any]) -> None:
    required = ["project", "output", "firms", "clients", "activity", "data_quality"]
    missing = [key for key in required if key not in config]
    if missing:
        raise ValueError(f"Missing config sections: {missing}")

    for size in ("small", "medium", "large"):
        block = config["firms"].get(size, {})
        count = int(block.get("count", 0))
        if count < 0:
            raise ValueError(f"firms.{size}.count cannot be negative")
        if count == 0:
            continue
        for dimension in ("offices", "employees", "clients"):
            value = block.get(dimension)
            if not isinstance(value, dict) or "min" not in value or "max" not in value:
                raise ValueError(f"firms.{size}.{dimension} must contain min and max")
            if int(value["min"]) < 0 or int(value["max"]) < int(value["min"]):
                raise ValueError(f"Invalid range at firms.{size}.{dimension}")

    if int(config["project"]["months"]) <= 0:
        raise ValueError("project.months must be positive")

    minimums = config.get("data_quality", {}).get(
        "minimum_issues_per_rule",
        {},
    )
    for rule_code, value in minimums.items():
        if int(value) < 0:
            raise ValueError(
                f"data_quality.minimum_issues_per_rule.{rule_code} "
                "cannot be negative"
            )


def load_effective_config(
    base_path: Path,
    profile_path: Path | None = None,
    scenario_path: Path | None = None,
    overrides: list[str] | None = None,
) -> dict[str, Any]:
    config = load_yaml(base_path)
    config = deep_merge(config, load_yaml(profile_path))
    config = deep_merge(config, load_yaml(scenario_path))
    for item in overrides or []:
        apply_dotted_override(config, item)
    validate_config(config)
    return config


def dump_config(config: dict[str, Any], path: Path) -> None:
    path.write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
