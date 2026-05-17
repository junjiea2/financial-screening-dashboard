"""Write a small report for prefiltered universe files."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成预筛报告")
    parser.add_argument("--investable", default="data/universe/investable_universe.csv")
    parser.add_argument("--rejected", default="data/universe/rejected_universe.csv")
    parser.add_argument("--output", default="data/reports/prefilter_report.txt")
    return parser.parse_args()


def read_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    args = parse_args()
    investable = read_rows(args.investable)
    rejected = read_rows(args.rejected)
    lines = ["Prefilter Report", ""]
    lines.append(f"Investable: {len(investable)}")
    lines.append(f"Rejected: {len(rejected)}")
    lines.append("")
    lines.append("Investable by market:")
    for market, count in sorted(Counter(row["market"] for row in investable).items()):
        lines.append(f"  {market}: {count}")
    lines.append("")
    lines.append("Rejected by reason:")
    for reason, count in Counter(row["prefilter_reason"] for row in rejected).most_common():
        lines.append(f"  {reason}: {count}")
    lines.append("")
    lines.append("Investable by industry model:")
    for profile, count in Counter(row["industry_profile"] for row in investable).most_common():
        lines.append(f"  {profile}: {count}")
    Path(args.output).write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
