#!/usr/bin/env python3
"""Inspect a TDX gpcw zip/dat schema without a full import."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tdxhub.affair import Affair  # noqa: E402
from tdxhub.financial.financial import Financial  # noqa: E402


def _resolve_input(args: argparse.Namespace) -> Path:
    if args.path:
        path = Path(args.path)
        if not path.exists():
            raise FileNotFoundError(path)
        return path

    if not args.filename:
        raise ValueError("provide a local gpcw zip/dat path or --filename")

    downdir = Path(args.downdir)
    downdir.mkdir(parents=True, exist_ok=True)
    path = downdir / args.filename
    if not path.exists():
        Affair.fetch(downdir=str(downdir), filename=args.filename)
    if not path.exists():
        raise FileNotFoundError(path)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", help="Local gpcw .zip or .dat path")
    parser.add_argument("--filename", help="Remote gpcw filename to fetch before probing")
    parser.add_argument("--downdir", default="tmp", help="Download/cache directory for --filename")
    parser.add_argument("--sample-size", type=int, default=0, help="Sample stock rows for non-zero counts")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args(argv)

    path = _resolve_input(args)
    with path.open("rb") as fp:
        info = Financial().inspect(fp, sample_size=args.sample_size)

    if args.json:
        print(json.dumps(info, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    print(f"file: {path}")
    print(f"report_date: {info['report_date']}")
    print(f"stock_count: {info['stock_count']}")
    print(f"report_size: {info['report_size']}")
    print(f"report_fields_count: {info['report_fields_count']}")
    print(f"known_data_columns: {info['known_data_columns']}")
    print(f"placeholder_count: {info['placeholder_count']}")
    print(f"raw_tail_count: {info['raw_tail_count']}")
    if info["raw_tail_columns"]:
        print("raw_tail_columns: " + ", ".join(info["raw_tail_columns"]))
    if args.sample_size:
        print("sample:")
        for row in info["sample"]:
            print(
                f"  {row['code']}: non_zero={row['non_zero_fields']} "
                f"zero={row['zero_fields']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
