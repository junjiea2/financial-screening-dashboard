"""Fetch broad A-share and US ticker universes."""

from __future__ import annotations

import argparse

from universe_loader import (
    fetch_a_share_universe,
    fetch_us_universe,
    write_universe_csv,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="获取 A 股 / 美股股票池")
    parser.add_argument(
        "--markets",
        nargs="+",
        choices=["CN", "US"],
        default=["CN", "US"],
        help="要获取的市场，默认 CN US",
    )
    parser.add_argument("--output", default="data/universe/stock_universe.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = []
    if "US" in args.markets:
        try:
            rows.extend(fetch_us_universe())
        except Exception as exc:
            print(f"US universe fetch failed: {exc}")
    if "CN" in args.markets:
        try:
            rows.extend(fetch_a_share_universe())
        except Exception as exc:
            print(f"CN universe fetch failed: {exc}")
    write_universe_csv(rows, args.output)
    print(f"Wrote {len(rows)} symbols to {args.output}")


if __name__ == "__main__":
    main()
