"""Analyze raw fetch files, normalized data, and screening output."""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path


KEY_FIELDS = [
    "revenue",
    "net_income",
    "operating_cash_flow",
    "shareholders_equity",
    "asset_liability_ratio",
    "total_assets",
    "total_liabilities",
    "capital_expenditure",
    "goodwill",
    "ebit",
    "interest_expense",
    "dividends_paid",
    "roe",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成采集和筛选稳定性报告")
    parser.add_argument("--us-raw", required=True)
    parser.add_argument("--cn-raw", required=True)
    parser.add_argument("--full", required=True)
    parser.add_argument("--screening", required=True)
    parser.add_argument("--output", default="data/reports/stability_report_latest.txt")
    parser.add_argument("--us-time", default="")
    parser.add_argument("--cn-time", default="")
    return parser.parse_args()


def read_rows(path: str | Path) -> list[dict[str, str]]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def status_by_symbol(rows: list[dict[str, str]]) -> dict[str, set[str]]:
    statuses: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        statuses[row.get("status", "")].add(row.get("symbol", ""))
    return statuses


def append_status(lines: list[str], label: str, rows: list[dict[str, str]]) -> None:
    statuses = status_by_symbol(rows)
    total = sum(len(symbols) for symbols in statuses.values())
    lines.append(f"{label} symbol status:")
    if total == 0:
        lines.append("  no rows")
    for status, symbols in sorted(statuses.items()):
        count = len(symbols)
        lines.append(f"  {status or 'blank'}: {count} ({count / total:.1%})")
    lines.append(f"  total: {total}")
    source_counts = Counter(row.get("source", "") for row in rows if row.get("source"))
    if source_counts:
        lines.append("  sources:")
        for source, count in sorted(source_counts.items()):
            lines.append(f"    {source}: {count} raw rows")
    lines.append("")


def missing_ratios(rows: list[dict[str, str]], market: str) -> tuple[list[str], list[str]]:
    subset = [row for row in rows if row.get("market") == market]
    summary_lines = []
    field_lines = []
    denominator = len(subset) * len(KEY_FIELDS)
    missing = sum(1 for row in subset for field in KEY_FIELDS if not row.get(field))
    ratio = missing / denominator if denominator else 0
    summary_lines.append(
        f"{market} missing field ratio: {missing}/{denominator} ({ratio:.1%}) across {len(subset)} annual rows"
    )
    for field in KEY_FIELDS:
        field_missing = sum(1 for row in subset if not row.get(field))
        field_ratio = field_missing / len(subset) if subset else 0
        field_lines.append(
            f"  {market} {field}: {field_missing}/{len(subset)} ({field_ratio:.1%})"
        )
    return summary_lines, field_lines


def screening_distribution(path: str | Path) -> tuple[Counter[tuple[str, str]], Counter[tuple[str, str]]]:
    file_path = Path(path)
    quality: Counter[tuple[str, str]] = Counter()
    results: Counter[tuple[str, str]] = Counter()
    if not file_path.exists():
        return quality, results
    with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            return quality, results
        index = {name: i for i, name in enumerate(header)}
        market_i = index.get("市场", 1)
        quality_i = index.get("数据质量", 19)
        result_i = index.get("结果", 21)
        for row in reader:
            if len(row) <= max(market_i, quality_i, result_i):
                continue
            quality[(row[market_i], row[quality_i])] += 1
            results[(row[market_i], row[result_i])] += 1
    return quality, results


def main() -> None:
    args = parse_args()
    us_rows = read_rows(args.us_raw)
    cn_rows = read_rows(args.cn_raw)
    full_rows = read_rows(args.full)
    quality, results = screening_distribution(args.screening)

    lines = ["Pipeline Stability Report", ""]
    if args.us_time:
        lines.append(f"US time: {Path(args.us_time).read_text(encoding='utf-8-sig').strip()}")
    if args.cn_time:
        lines.append(f"CN time: {Path(args.cn_time).read_text(encoding='utf-8-sig').strip()}")
    if args.us_time or args.cn_time:
        lines.append("")

    append_status(lines, "US", us_rows)
    append_status(lines, "CN", cn_rows)
    lines.append(f"Normalized annual rows: {len(full_rows)}")

    all_field_lines: list[str] = []
    for market in ("US", "CN"):
        summary, fields = missing_ratios(full_rows, market)
        lines.extend(summary)
        all_field_lines.extend(fields)

    lines.append("")
    lines.append("Data quality distribution:")
    for (market, level), count in sorted(quality.items()):
        lines.append(f"  {market} {level}: {count}")

    lines.append("")
    lines.append("Screening result distribution:")
    for (market, result), count in sorted(results.items()):
        lines.append(f"  {market} {result}: {count}")

    lines.append("")
    lines.append("Field missing ratios:")
    lines.extend(all_field_lines)

    Path(args.output).write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
