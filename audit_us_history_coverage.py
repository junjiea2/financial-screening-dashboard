"""Audit US raw and normalized history coverage."""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_RAW = "data/raw/us_financials_raw_investable_all.csv"
DEFAULT_NORMALIZED = "data/normalized/full_financials_investable_all.csv"
DEFAULT_OUTPUT = "public/data/reports/us_history_coverage.csv"

IMPORTANT_FIELDS = (
    "revenue",
    "net_income",
    "operating_cash_flow",
    "shareholders_equity",
    "total_assets",
    "total_liabilities",
)

OUTPUT_COLUMNS = [
    "股票",
    "市场",
    "名称",
    "行业",
    "来源",
    "状态",
    "原始年份数",
    "标准化年份数",
    "完整年份数",
    "最早年份",
    "最新年份",
    "历史可信度",
    "缺失字段摘要",
    "来源摘要",
    "需补历史",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit US financial history coverage.")
    parser.add_argument("--raw", default=DEFAULT_RAW, help="Raw US financial CSV.")
    parser.add_argument("--normalized", default=DEFAULT_NORMALIZED, help="Normalized full financial CSV.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Coverage report CSV.")
    return parser.parse_args()


def read_rows(path: str | Path) -> list[dict[str, str]]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: str | Path, rows: list[dict[str, object]]) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({header: row.get(header, "") for header in OUTPUT_COLUMNS})


def _has_value(row: dict[str, str], field: str) -> bool:
    value = row.get(field)
    return value is not None and str(value).strip() not in {"", "-"}


def is_complete_year(row: dict[str, str]) -> bool:
    has_roe_or_equity = _has_value(row, "roe") or _has_value(row, "shareholders_equity")
    has_balance_anchor = _has_value(row, "asset_liability_ratio") or (
        _has_value(row, "total_assets") and _has_value(row, "total_liabilities")
    )
    return (
        _has_value(row, "revenue")
        and _has_value(row, "net_income")
        and has_roe_or_equity
        and has_balance_anchor
    )


def history_confidence(complete_years: int) -> str:
    if complete_years >= 10:
        return "A 完整历史"
    if complete_years >= 6:
        return "B 中等历史"
    if complete_years >= 1:
        return "C 短历史"
    return "未知"


def year_set(rows: list[dict[str, str]]) -> set[int]:
    years: set[int] = set()
    for row in rows:
        try:
            years.add(int(row.get("year", "")))
        except ValueError:
            pass
    return years


def missing_summary(rows: list[dict[str, str]]) -> str:
    missing = Counter()
    for row in rows:
        for field in IMPORTANT_FIELDS:
            if not _has_value(row, field):
                missing[field] += 1
    if not missing:
        return "-"
    return "；".join(f"{field}:{count}" for field, count in missing.most_common())


def source_summary(rows: list[dict[str, str]]) -> str:
    counts = Counter(row.get("source") or "-" for row in rows)
    return "；".join(f"{source}:{count}" for source, count in sorted(counts.items()))


def build_coverage_report(
    raw_rows: list[dict[str, str]],
    normalized_rows: list[dict[str, str]],
) -> list[dict[str, object]]:
    raw_by_symbol: dict[str, list[dict[str, str]]] = defaultdict(list)
    normalized_by_symbol: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in raw_rows:
        if row.get("market") == "US" and row.get("symbol"):
            raw_by_symbol[row["symbol"]].append(row)
    for row in normalized_rows:
        if row.get("market") == "US" and row.get("symbol"):
            normalized_by_symbol[row["symbol"]].append(row)

    symbols = sorted(set(raw_by_symbol) | set(normalized_by_symbol))
    report: list[dict[str, object]] = []
    for symbol in symbols:
        raw_symbol_rows = raw_by_symbol.get(symbol, [])
        normalized_symbol_rows = normalized_by_symbol.get(symbol, [])
        base = normalized_symbol_rows[0] if normalized_symbol_rows else (raw_symbol_rows[0] if raw_symbol_rows else {})
        raw_years = year_set([row for row in raw_symbol_rows if row.get("status") == "ok"])
        normalized_years = year_set(normalized_symbol_rows)
        complete_years = sum(1 for row in normalized_symbol_rows if is_complete_year(row))
        all_years = sorted(normalized_years or raw_years)
        statuses = Counter(row.get("status") or "-" for row in raw_symbol_rows)
        status = "；".join(f"{item}:{count}" for item, count in sorted(statuses.items())) if statuses else "-"
        report.append(
            {
                "股票": symbol,
                "市场": "US",
                "名称": base.get("name", ""),
                "行业": base.get("industry", ""),
                "来源": source_summary(raw_symbol_rows),
                "状态": status,
                "原始年份数": len(raw_years),
                "标准化年份数": len(normalized_years),
                "完整年份数": complete_years,
                "最早年份": all_years[0] if all_years else "",
                "最新年份": all_years[-1] if all_years else "",
                "历史可信度": history_confidence(complete_years),
                "缺失字段摘要": missing_summary(normalized_symbol_rows),
                "来源摘要": source_summary(raw_symbol_rows),
                "需补历史": "是" if complete_years < 8 else "否",
            }
        )

    report.sort(key=lambda row: (int(row["完整年份数"]), int(row["标准化年份数"]), str(row["股票"])))
    return report


def main() -> None:
    args = parse_args()
    report = build_coverage_report(read_rows(args.raw), read_rows(args.normalized))
    write_rows(args.output, report)
    short_history = sum(1 for row in report if row["历史可信度"] == "C 短历史")
    full_history = sum(1 for row in report if row["历史可信度"] == "A 完整历史")
    print(f"Wrote {len(report)} US history coverage rows to {args.output}")
    print(f"US full-history rows: {full_history}")
    print(f"US short-history rows: {short_history}")


if __name__ == "__main__":
    main()
