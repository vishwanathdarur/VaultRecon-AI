from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from .config import dump_config, load_effective_config
from .generator import AccountingDatasetGenerator
from .validators import validate_dataset


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="accounting-data-generator")
    sub = parser.add_subparsers(dest="command", required=True)

    generate = sub.add_parser(
        "generate",
        help="Generate a configured synthetic accounting dataset.",
    )
    generate.add_argument(
        "--config",
        type=Path,
        default=Path("config/config.yaml"),
    )
    generate.add_argument("--profile", type=Path)
    generate.add_argument("--scenario", type=Path)
    generate.add_argument("--output", type=Path)
    generate.add_argument(
        "--set",
        dest="overrides",
        action="append",
        default=[],
        help="Override a value with dotted.path=value. May be repeated.",
    )

    validate = sub.add_parser(
        "validate",
        help="Validate an existing generated dataset.",
    )
    validate.add_argument("--input", required=True, type=Path)

    show = sub.add_parser(
        "show-config",
        help="Print the merged effective configuration.",
    )
    show.add_argument(
        "--config",
        type=Path,
        default=Path("config/config.yaml"),
    )
    show.add_argument("--profile", type=Path)
    show.add_argument("--scenario", type=Path)
    show.add_argument(
        "--set",
        dest="overrides",
        action="append",
        default=[],
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.command == "validate":
        report = validate_dataset(args.input)
        print(json.dumps(report, indent=2))
        raise SystemExit(0 if report["passed"] else 1)

    config = load_effective_config(
        base_path=args.config,
        profile_path=getattr(args, "profile", None),
        scenario_path=getattr(args, "scenario", None),
        overrides=getattr(args, "overrides", []),
    )

    if args.command == "show-config":
        print(
            yaml.safe_dump(
                config,
                sort_keys=False,
                allow_unicode=True,
            )
        )
        return

    output_dir = args.output or Path(config["output"]["directory"])
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = AccountingDatasetGenerator(
        config,
        output_dir,
    ).generate()
    dump_config(config, output_dir / "effective_config.yaml")

    report = None
    if bool(config["output"].get("run_validation", True)):
        report = validate_dataset(output_dir)

    print(
        json.dumps(
            {"manifest": manifest, "validation": report},
            indent=2,
        )
    )
    if report is not None and not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
