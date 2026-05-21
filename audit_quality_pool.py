"""Audit quality-pool distribution, capped candidates, and calibration errors."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from quality_pool_rank import level_from_score, number, score_details


DEFAULT_QUALITY_POOL = "public/data/screening/quality_pool_investable_all.csv"
DEFAULT_CALIBRATION_REPORT = "data/samples/calibration_report.csv"
DEFAULT_OUTPUT_DIR = "public/data/reports"

DISTRIBUTION_COLUMNS = [
    "市场",
    "行业模型",
    "优质池等级",
    "历史可信度",
    "数量",
    "平均综合优质分",
    "平均规则质量分",
    "平均数据质量分",
    "AI优质候选数量",
    "AI已评估数量",
    "短历史受限数量",
    "短历史封顶生效数量",
    "去短历史封顶可升核心数量",
]

CAPPED_COLUMNS = [
    "股票",
    "市场",
    "名称",
    "行业模型",
    "优质池等级",
    "综合优质分",
    "基础理论分",
    "去短历史封顶分",
    "去短历史封顶等级",
    "是否因历史数据封顶",
    "是否因历史数据受限",
    "是否因排雷状态扣分",
    "是否因规则AI分歧扣分",
    "封顶原因",
    "规则质量评级",
    "规则质量分",
    "AI评级",
    "数据年数",
    "历史可信度",
    "数据质量",
    "数据质量分",
    "风险扣分",
    "质量理由",
    "综合观察",
]

CALIBRATION_SUMMARY_COLUMNS = [
    "错误类型",
    "预期类别",
    "数量",
    "样本",
]

LEVEL_ORDER = {
    "核心优质池": 0,
    "优质池": 1,
    "可研究池": 2,
    "观察池": 3,
    "高争议池": 4,
    "未入池": 5,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate quality-pool audit reports.")
    parser.add_argument("--quality-pool", default=DEFAULT_QUALITY_POOL, help="Quality pool CSV.")
    parser.add_argument("--calibration-report", default=DEFAULT_CALIBRATION_REPORT, help="Calibration report CSV.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Directory for audit CSV outputs.")
    return parser.parse_args()


def read_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: str | Path, headers: list[str], rows: list[dict[str, object]]) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({header: row.get(header, "") for header in headers})


def history_confidence(value: str | int | float | None) -> str:
    years = int(number(str(value), default=0)) if value not in {None, ""} else 0
    if years >= 10:
        return "A 完整历史"
    if years >= 5:
        return "B 中等历史"
    if years >= 1:
        return "C 短历史"
    return "未知"


def average(values: list[float]) -> str:
    if not values:
        return "-"
    return f"{sum(values) / len(values):.1f}"


def yes_no(value: bool) -> str:
    return "是" if value else "否"


def _append_number(group: dict[str, object], key: str, value: str | None) -> None:
    parsed = number(value, default=-1)
    if parsed >= 0:
        group.setdefault(key, []).append(parsed)


def build_distribution(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    groups: dict[tuple[str, str, str, str], dict[str, object]] = {}
    for row in rows:
        market = row.get("市场", "-") or "-"
        industry = row.get("行业模型", "-") or "-"
        level = row.get("优质池等级", "-") or "-"
        confidence = history_confidence(row.get("数据年数"))
        key = (market, industry, level, confidence)
        group = groups.setdefault(
            key,
            {
                "市场": market,
                "行业模型": industry,
                "优质池等级": level,
                "历史可信度": confidence,
                "数量": 0,
                "AI优质候选数量": 0,
                "AI已评估数量": 0,
                "短历史受限数量": 0,
                "短历史封顶生效数量": 0,
                "去短历史封顶可升核心数量": 0,
            },
        )
        group["数量"] = int(group["数量"]) + 1
        _append_number(group, "_综合优质分", row.get("综合优质分"))
        _append_number(group, "_规则质量分", row.get("规则质量分"))
        _append_number(group, "_数据质量分", row.get("数据质量分"))

        ai_rating = row.get("AI评级") or row.get("AI判断") or ""
        if ai_rating and ai_rating not in {"-", "未评估"}:
            group["AI已评估数量"] = int(group["AI已评估数量"]) + 1
        if ai_rating == "优质候选":
            group["AI优质候选数量"] = int(group["AI优质候选数量"]) + 1

        details = score_details(row)
        if details["短历史受限"]:
            group["短历史受限数量"] = int(group["短历史受限数量"]) + 1
        if details["短历史封顶生效"]:
            group["短历史封顶生效数量"] = int(group["短历史封顶生效数量"]) + 1
        if level != "核心优质池" and details["去短历史封顶等级"] == "核心优质池":
            group["去短历史封顶可升核心数量"] = int(group["去短历史封顶可升核心数量"]) + 1

    output: list[dict[str, object]] = []
    for group in groups.values():
        group["平均综合优质分"] = average(group.pop("_综合优质分", []))
        group["平均规则质量分"] = average(group.pop("_规则质量分", []))
        group["平均数据质量分"] = average(group.pop("_数据质量分", []))
        output.append(group)
    output.sort(
        key=lambda row: (
            str(row["市场"]),
            str(row["行业模型"]),
            LEVEL_ORDER.get(str(row["优质池等级"]), 99),
            str(row["历史可信度"]),
        )
    )
    return output


def cap_reasons(row: dict[str, str], details: dict[str, object]) -> list[str]:
    reasons: list[str] = []
    if details["短历史封顶生效"]:
        reasons.append("短历史封顶生效")
    elif details["短历史受限"]:
        reasons.append("短历史受限")
    if details["排雷状态扣分"]:
        reasons.append("排雷状态扣分")
    if details["规则AI分歧扣分"]:
        reasons.append("规则AI分歧扣分")
    if not reasons and level_from_score(row, number(row.get("综合优质分"), default=0)) != "核心优质池":
        reasons.append("综合分未达核心阈值")
    return reasons


def build_capped_candidates(rows: list[dict[str, str]], min_rule_quality: float = 88) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for row in rows:
        ai_rating = row.get("AI评级") or row.get("AI判断") or ""
        rule_quality = number(row.get("规则质量分"), default=0)
        has_high_quality_signal = (
            rule_quality >= min_rule_quality
            or row.get("规则质量评级") == "优质候选"
            or ai_rating == "优质候选"
        )
        if not has_high_quality_signal or row.get("优质池等级") == "核心优质池":
            continue
        details = score_details(row)
        reasons = cap_reasons(row, details)
        candidates.append(
            {
                "股票": row.get("股票", ""),
                "市场": row.get("市场", ""),
                "名称": row.get("名称", ""),
                "行业模型": row.get("行业模型", ""),
                "优质池等级": row.get("优质池等级", ""),
                "综合优质分": row.get("综合优质分", ""),
                "基础理论分": details["基础理论分"],
                "去短历史封顶分": details["去短历史封顶分"],
                "去短历史封顶等级": details["去短历史封顶等级"],
                "是否因历史数据封顶": yes_no(bool(details["短历史封顶生效"])),
                "是否因历史数据受限": yes_no(bool(details["短历史受限"])),
                "是否因排雷状态扣分": yes_no(bool(details["排雷状态扣分"])),
                "是否因规则AI分歧扣分": yes_no(bool(details["规则AI分歧扣分"])),
                "封顶原因": "；".join(reasons) if reasons else "-",
                "规则质量评级": row.get("规则质量评级", ""),
                "规则质量分": row.get("规则质量分", ""),
                "AI评级": ai_rating or "-",
                "数据年数": row.get("数据年数", ""),
                "历史可信度": history_confidence(row.get("数据年数")),
                "数据质量": row.get("数据质量", ""),
                "数据质量分": row.get("数据质量分", ""),
                "风险扣分": row.get("风险扣分", ""),
                "质量理由": row.get("质量理由", ""),
                "综合观察": row.get("综合观察", ""),
            }
        )
    candidates.sort(
        key=lambda row: (
            number(str(row["去短历史封顶分"]), default=0),
            number(str(row["规则质量分"]), default=0),
            number(str(row["综合优质分"]), default=0),
        ),
        reverse=True,
    )
    return candidates


def infer_error_type(row: dict[str, str]) -> str:
    if row.get("错误类型"):
        return row["错误类型"]
    if row.get("校准通过") == "是":
        return "pass"
    expected = row.get("预期类别", "")
    if expected in {"高质量", "高质量样本"}:
        return "false_negative"
    if expected in {"高风险", "高风险样本", "争议成长", "争议样本", "争议"}:
        return "false_positive"
    return "unknown"


def build_calibration_error_summary(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    groups: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        error_type = infer_error_type(row)
        expected = row.get("预期类别", "-") or "-"
        key = (error_type, expected)
        group = groups.setdefault(
            key,
            {
                "错误类型": error_type,
                "预期类别": expected,
                "数量": 0,
                "_samples": [],
            },
        )
        group["数量"] = int(group["数量"]) + 1
        if len(group["_samples"]) < 8:
            group["_samples"].append(f"{row.get('市场', '')} {row.get('股票', '')}".strip())
    output: list[dict[str, object]] = []
    for group in groups.values():
        group["样本"] = "；".join(group.pop("_samples", []))
        output.append(group)
    output.sort(key=lambda row: (str(row["错误类型"]), str(row["预期类别"])))
    return output


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    quality_rows = read_rows(args.quality_pool)
    calibration_rows = read_rows(args.calibration_report)

    distribution = build_distribution(quality_rows)
    capped = build_capped_candidates(quality_rows)
    calibration_summary = build_calibration_error_summary(calibration_rows)

    write_rows(output_dir / "quality_pool_distribution.csv", DISTRIBUTION_COLUMNS, distribution)
    write_rows(output_dir / "capped_quality_candidates.csv", CAPPED_COLUMNS, capped)
    write_rows(output_dir / "calibration_error_summary.csv", CALIBRATION_SUMMARY_COLUMNS, calibration_summary)

    us_short_limited = sum(
        1 for row in quality_rows if row.get("市场") == "US" and history_confidence(row.get("数据年数")) == "C 短历史"
    )
    us_short_cap_applied = sum(
        1 for row in quality_rows if row.get("市场") == "US" and bool(score_details(row)["短历史封顶生效"])
    )
    move_to_core = sum(
        1
        for row in quality_rows
        if row.get("优质池等级") != "核心优质池" and score_details(row)["去短历史封顶等级"] == "核心优质池"
    )
    research_to_core = sum(
        1
        for row in quality_rows
        if row.get("优质池等级") == "可研究池" and score_details(row)["去短历史封顶等级"] == "核心优质池"
    )
    print(f"Wrote {len(distribution)} distribution rows to {output_dir / 'quality_pool_distribution.csv'}")
    print(f"Wrote {len(capped)} capped candidate rows to {output_dir / 'capped_quality_candidates.csv'}")
    print(f"Wrote {len(calibration_summary)} calibration summary rows to {output_dir / 'calibration_error_summary.csv'}")
    print(f"US short-history quality-pool rows: {us_short_limited}")
    print(f"US rows where short-history cap is binding: {us_short_cap_applied}")
    print(f"Non-core rows that would reach 核心优质池 without short-history cap: {move_to_core}")
    print(f"可研究池 rows that would reach 核心优质池 without short-history cap: {research_to_core}")


if __name__ == "__main__":
    main()
