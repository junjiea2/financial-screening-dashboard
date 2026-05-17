"""Select a balanced batch of stocks for AI independent evaluation."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select AI evaluation candidates.")
    parser.add_argument("--rules", required=True, help="Rule dual-track CSV.")
    parser.add_argument("--financials", required=True, help="Normalized financial CSV.")
    parser.add_argument("--output-financials", required=True, help="Selected normalized CSV.")
    parser.add_argument("--output-symbols", required=True, help="Selected symbol list CSV.")
    parser.add_argument("--exclude-ai", default="", help="Existing AI evaluation CSV to exclude.")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--cn-share", type=int, default=60)
    return parser.parse_args()


def read_dicts(path: str | Path) -> list[dict[str, str]]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def number(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return -1


def rank_key(row: dict[str, str]) -> tuple[int, float, float]:
    quality_rank = {"优质候选": 2, "可跟踪": 1}.get(row.get("规则质量评级", ""), 0)
    return (
        quality_rank,
        number(row.get("规则质量分", "")),
        number(row.get("数据质量分", "")),
    )


def existing_keys(path: str) -> set[tuple[str, str]]:
    if not path:
        return set()
    rows = read_dicts(path)
    return {
        (row.get("市场", ""), row.get("股票", ""))
        for row in rows
        if row.get("AI评级")
    }


def select_candidates(
    rows: list[dict[str, str]],
    limit: int,
    cn_share: int,
    excluded: set[tuple[str, str]],
) -> list[dict[str, str]]:
    eligible = [
        row
        for row in rows
        if row.get("规则质量评级") in {"优质候选", "可跟踪"}
        and row.get("结果") not in {"排除", "数据不足", "需专项分析"}
        and (row.get("市场", ""), row.get("股票", "")) not in excluded
    ]
    eligible.sort(key=rank_key, reverse=True)
    cn_limit = min(cn_share, limit)
    us_limit = max(0, limit - cn_limit)
    selected: list[dict[str, str]] = []
    selected.extend([row for row in eligible if row.get("市场") == "CN"][:cn_limit])
    selected.extend([row for row in eligible if row.get("市场") == "US"][:us_limit])
    if len(selected) < limit:
        seen = {(row["市场"], row["股票"]) for row in selected}
        selected.extend(
            row
            for row in eligible
            if (row["市场"], row["股票"]) not in seen
        )
    return selected[:limit]


def main() -> None:
    args = parse_args()
    rule_rows = read_dicts(args.rules)
    excluded = existing_keys(args.exclude_ai)
    selected = select_candidates(rule_rows, args.limit, args.cn_share, excluded)
    selected_keys = {(row["市场"], row["股票"]) for row in selected}

    financial_rows = read_dicts(args.financials)
    picked_financials = [
        row for row in financial_rows if (row.get("market"), row.get("symbol")) in selected_keys
    ]

    financial_headers = list(financial_rows[0].keys()) if financial_rows else []
    with Path(args.output_financials).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=financial_headers)
        writer.writeheader()
        writer.writerows(picked_financials)

    symbol_headers = [
        "股票",
        "市场",
        "名称",
        "结果",
        "分数",
        "规则质量评级",
        "规则质量分",
        "数据质量",
    ]
    with Path(args.output_symbols).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=symbol_headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(selected)

    print(
        f"Selected {len(selected)} stocks and {len(picked_financials)} annual rows "
        f"to {args.output_financials}; excluded existing AI rows: {len(excluded)}"
    )


if __name__ == "__main__":
    main()
