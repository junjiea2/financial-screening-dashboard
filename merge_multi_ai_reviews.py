"""Merge multiple AI review CSVs into consensus and disagreement signals."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


CONSENSUS_COLUMNS = [
    "AI共识评级",
    "AI共识度",
    "AI分歧状态",
    "AI复核模型数",
    "AI评级明细",
]

RATING_SCORE = {
    "优质候选": 100,
    "可跟踪": 75,
    "谨慎观察": 45,
    "排除": 0,
    "数据不足": 0,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge multiple AI review tracks.")
    parser.add_argument(
        "--input",
        action="append",
        required=True,
        help="AI review CSV as label=path, e.g. deepseek=data/ai/deepseek.csv",
    )
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def read_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def identity(row: dict[str, str]) -> tuple[str, str]:
    return row.get("市场", ""), row.get("股票", "")


def parse_input(value: str) -> tuple[str, str]:
    if "=" not in value:
        path = value
        return Path(path).stem, path
    label, path = value.split("=", 1)
    return label.strip(), path.strip()


def consensus_rating(avg_score: float) -> str:
    if avg_score >= 88:
        return "优质候选"
    if avg_score >= 62:
        return "可跟踪"
    if avg_score >= 30:
        return "谨慎观察"
    return "排除"


def merge_reviews(review_groups: dict[tuple[str, str], list[tuple[str, dict[str, str]]]]) -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    for key, reviews in review_groups.items():
        market, symbol = key
        ratings = [(label, row.get("AI评级", "")) for label, row in reviews if row.get("AI评级")]
        if not ratings:
            continue
        scores = [RATING_SCORE.get(rating, 40) for _, rating in ratings]
        avg = sum(scores) / len(scores)
        top_rating_count = max(sum(1 for _, rating in ratings if rating == candidate) for candidate in {rating for _, rating in ratings})
        agreement = top_rating_count / len(ratings)
        if agreement == 1:
            disagreement = "一致"
        elif max(scores) - min(scores) >= 55:
            disagreement = "明显分歧"
        else:
            disagreement = "轻微分歧"

        first = reviews[0][1]
        row = {
            "股票": symbol,
            "市场": market,
            "名称": first.get("名称", "-"),
            "行业": first.get("行业", "-"),
            "AI共识评级": consensus_rating(avg),
            "AI共识度": f"{agreement:.0%}",
            "AI分歧状态": disagreement,
            "AI复核模型数": str(len(ratings)),
            "AI评级明细": "；".join(f"{label}:{rating}" for label, rating in ratings),
        }
        merged.append(row)

    merged.sort(
        key=lambda row: (
            RATING_SCORE.get(row["AI共识评级"], 0),
            int(row["AI共识度"].rstrip("%")),
            row["市场"],
            row["股票"],
        ),
        reverse=True,
    )
    return merged


def main() -> None:
    args = parse_args()
    groups: dict[tuple[str, str], list[tuple[str, dict[str, str]]]] = {}
    for spec in args.input:
        label, path = parse_input(spec)
        for row in read_rows(path):
            if row.get("AI评级"):
                groups.setdefault(identity(row), []).append((label, row))

    rows = merge_reviews(groups)
    with Path(args.output).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CONSENSUS_COLUMNS + ["股票", "市场", "名称", "行业"], extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} multi-AI consensus rows to {args.output}")


if __name__ == "__main__":
    main()
