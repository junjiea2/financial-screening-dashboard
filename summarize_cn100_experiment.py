"""Summarize the CN 100 strict-rule and AI-only experiment."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path


def read_csv(path: str) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    strict_path = Path("data/screening/screening_result_cn_100_strict.csv")
    ai_path = Path("data/ai/ai_independent_cn_100.csv")

    if strict_path.exists():
        rows = read_csv(str(strict_path))
        result_col = "结果" if "结果" in rows[0] else list(rows[0].keys())[21]
        print("Strict rule result distribution:")
        for key, value in Counter(row[result_col] for row in rows).most_common():
            print(f"  {key}: {value}")
    else:
        print("Missing data/screening/screening_result_cn_100_strict.csv")

    if ai_path.exists():
        rows = read_csv(str(ai_path))
        print("\nAI-only rating distribution:")
        for key, value in Counter(row["AI评级"] for row in rows).most_common():
            print(f"  {key}: {value}")
        print("\nTop AI candidates:")
        for row in rows:
            if row["AI评级"] in {"优质候选", "可跟踪"}:
                print(f"  {row['股票']} {row['名称']} | {row['AI评级']} | {row['AI理由']}")
    else:
        print("\nMissing data/ai/ai_independent_cn_100.csv. Run scripts/run_ai_cn_100.ps1 first.")


if __name__ == "__main__":
    main()
