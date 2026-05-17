"""Classify a ticker universe with the industry model."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from industry_model import classify_industry
from models import StockFinancials


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="给股票池打行业模型标签")
    parser.add_argument("--input", default="data/universe/stock_universe.csv")
    parser.add_argument("--output", default="data/universe/classified_universe.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with Path(args.input).open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    headers = [
        "symbol",
        "market",
        "name",
        "exchange",
        "industry",
        "industry_profile",
        "core_metrics",
        "source",
    ]
    output_rows = []
    for row in rows:
        stock = StockFinancials(
            symbol=row.get("symbol", ""),
            market=row.get("market", ""),
            name=row.get("name") or None,
            industry=row.get("industry") or None,
        )
        profile = classify_industry(stock)
        output_rows.append(
            {
                "symbol": row.get("symbol", ""),
                "market": row.get("market", ""),
                "name": row.get("name", ""),
                "exchange": row.get("exchange", ""),
                "industry": row.get("industry", ""),
                "industry_profile": profile.label,
                "core_metrics": "、".join(profile.core_metrics),
                "source": row.get("source", ""),
            }
        )

    with Path(args.output).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(output_rows)
    print(f"Wrote {len(output_rows)} classified symbols to {args.output}")


if __name__ == "__main__":
    main()
