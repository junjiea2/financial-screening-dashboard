"""Merge rule-based minefield screening with AI-only quality evaluation."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


AI_COLUMNS = ["AI评级", "AI置信度", "AI理由", "AI风险", "AI关注点", "AI模型"]
MERGE_COLUMNS = ["规则AI分歧", "综合观察"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge rule and AI screening tracks.")
    parser.add_argument("--rules", required=True, help="Rule screening CSV.")
    parser.add_argument("--ai", required=True, help="AI-only evaluation CSV.")
    parser.add_argument("--output", required=True, help="Merged dual-track CSV.")
    return parser.parse_args()


def read_rows(path: str | Path) -> tuple[list[str], list[dict[str, str]]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def identity(row: dict[str, str]) -> str:
    return f"{row.get('市场', '')}_{row.get('股票', '')}"


def disagreement(rule_row: dict[str, str], ai_row: dict[str, str] | None) -> tuple[str, str]:
    if ai_row is None:
        return "未评估", "暂无AI独立评估"

    mine = rule_row.get("结果", "")
    rule_quality = rule_row.get("规则质量评级", "")
    ai_rating = ai_row.get("AI评级", "")

    if mine == "排除" and ai_rating in {"优质候选", "可跟踪"}:
        return "是", "规则排雷较严，AI认为可能存在继续跟踪价值"
    if rule_quality == "优质候选" and ai_rating in {"谨慎观察", "排除"}:
        return "是", "规则质量分较高，但AI更关注风险，需要人工复核"
    if ai_rating == "优质候选" and rule_quality != "优质候选":
        return "是", "AI认为质量突出，规则侧可能因单项风险保守处理"
    if ai_rating == "排除" and mine != "排除":
        return "是", "AI认为质量较弱，规则侧未完全排除"
    if rule_quality == ai_rating:
        return "否", "规则质量评级与AI评级一致"
    return "轻微", "规则和AI评级不完全一致，可作为人工复核优先项"


def main() -> None:
    args = parse_args()
    rule_headers, rule_rows = read_rows(args.rules)
    _, ai_rows = read_rows(args.ai)
    ai_by_id = {identity(row): row for row in ai_rows}

    output_headers = rule_headers + [
        column for column in AI_COLUMNS + MERGE_COLUMNS if column not in rule_headers
    ]
    merged: list[dict[str, str]] = []
    for rule_row in rule_rows:
        row = dict(rule_row)
        ai_row = ai_by_id.get(identity(rule_row))
        if ai_row:
            for column in AI_COLUMNS:
                row[column] = ai_row.get(column, "")
        else:
            for column in AI_COLUMNS:
                row[column] = ""
        row["规则AI分歧"], row["综合观察"] = disagreement(rule_row, ai_row)
        merged.append(row)

    with Path(args.output).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(merged)
    print(f"Wrote {len(merged)} dual-track rows to {args.output}")


if __name__ == "__main__":
    main()
