"""Compare prefilter impact between two pipeline reports."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="对比预筛前后稳定性报告")
    parser.add_argument("--before", default="data/reports/stability_report_500.txt")
    parser.add_argument("--after", default="data/reports/stability_report_investable_500.txt")
    parser.add_argument("--output", default="data/reports/prefilter_impact_report.txt")
    return parser.parse_args()


def extract(text: str, label: str, default: str = "-") -> str:
    match = re.search(label, text)
    return match.group(1) if match else default


def metrics(path: str | Path) -> dict[str, str]:
    text = Path(path).read_text(encoding="utf-8")
    return {
        "us_ok": extract(text, r"US symbol status:[\s\S]*?ok: (\d+).*?\n"),
        "us_error": extract(text, r"US symbol status:[\s\S]*?error: (\d+).*?\n"),
        "us_skipped": extract(text, r"US symbol status:[\s\S]*?skipped: (\d+).*?\n", "0"),
        "cn_ok": extract(text, r"CN symbol status:[\s\S]*?ok: (\d+).*?\n"),
        "cn_error": extract(text, r"CN symbol status:[\s\S]*?error: (\d+).*?\n"),
        "normalized_rows": extract(text, r"Normalized annual rows: (\d+)"),
        "us_medium": extract(text, r"US Medium: (\d+)"),
        "us_low": extract(text, r"US Low: (\d+)"),
        "us_insufficient": extract(text, r"US Insufficient: (\d+)"),
        "us_pass": extract(text, r"US 通过: (\d+)"),
        "us_warn": extract(text, r"US 警惕: (\d+)"),
        "us_exclude": extract(text, r"US 排除: (\d+)"),
        "us_data_missing": extract(text, r"US 数据不足: (\d+)"),
    }


def main() -> None:
    args = parse_args()
    before = metrics(args.before)
    after = metrics(args.after)
    rows = [
        ("US ok", "us_ok"),
        ("US skipped", "us_skipped"),
        ("US error", "us_error"),
        ("CN ok", "cn_ok"),
        ("CN error", "cn_error"),
        ("Normalized rows", "normalized_rows"),
        ("US Medium", "us_medium"),
        ("US Low", "us_low"),
        ("US Insufficient", "us_insufficient"),
        ("US 通过", "us_pass"),
        ("US 警惕", "us_warn"),
        ("US 排除", "us_exclude"),
        ("US 数据不足", "us_data_missing"),
    ]
    lines = ["Prefilter Impact Report", "", "Metric | Before | After", "--- | ---: | ---:"]
    for label, key in rows:
        lines.append(f"{label} | {before[key]} | {after[key]}")
    Path(args.output).write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
