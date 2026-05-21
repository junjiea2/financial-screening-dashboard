"""Evaluate known calibration stocks against current screening outputs."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


DEFAULT_CALIBRATION = "data/samples/calibration_stocks.csv"
DEFAULT_SCREENING = "public/data/screening/dual_track_investable_all_ai_quality_all.csv"
DEFAULT_QUALITY_POOL = "public/data/screening/quality_pool_investable_all.csv"
DEFAULT_OUTPUT = "data/samples/calibration_report.csv"

REPORT_COLUMNS = [
    "股票",
    "市场",
    "名称",
    "预期类别",
    "校准通过",
    "错误类型",
    "失败原因",
    "当前结果",
    "规则质量评级",
    "规则质量分",
    "AI评级",
    "数据年数",
    "数据质量分",
    "数据质量",
    "综合优质分",
    "优质池等级",
    "入选来源",
    "风险扣分",
    "综合观察",
    "校准说明",
]

POOL_LEVEL_RANK = {
    "未入池": 0,
    "": 0,
    "-": 0,
    "观察池": 1,
    "高争议池": 1,
    "可研究池": 2,
    "优质池": 3,
    "核心优质池": 4,
}
BAD_HIGH_QUALITY_RESULTS = {"排除", "数据不足", "需专项分析"}
NEGATIVE_AI_RATINGS = {"排除", "建议排除", "数据不足"}
POSITIVE_AI_RATINGS = {"优质候选", "通过复核"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate screening quality with fixed calibration samples.")
    parser.add_argument("--calibration", default=DEFAULT_CALIBRATION, help="Known calibration stock CSV.")
    parser.add_argument("--screening", default=DEFAULT_SCREENING, help="Current dual-track screening CSV.")
    parser.add_argument("--quality-pool", default=DEFAULT_QUALITY_POOL, help="Current quality pool CSV.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Calibration report CSV.")
    return parser.parse_args()


def read_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: str | Path, rows: list[dict[str, str]]) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def stock_key(row: dict[str, str]) -> tuple[str, str]:
    market = (row.get("市场") or "").strip().upper()
    symbol = (row.get("股票") or "").strip().upper()
    return market, symbol


def index_by_stock(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {stock_key(row): row for row in rows if stock_key(row) != ("", "")}


def split_cell(value: str | None) -> set[str]:
    text = (value or "").strip()
    if not text:
        return set()
    for separator in ("|", "；", ";", "，", ",", "\n"):
        text = text.replace(separator, "|")
    return {item.strip() for item in text.split("|") if item.strip()}


def normalize_result(value: str | None) -> str:
    text = (value or "").strip()
    return "警惕" if text == "需关注" else text


def pool_rank(level: str | None) -> int:
    return POOL_LEVEL_RANK.get((level or "").strip(), 0)


def get_ai_rating(row: dict[str, str] | None) -> str:
    if not row:
        return ""
    return (row.get("AI评级") or row.get("AI判断") or "").strip()


def error_type_for(expected: str, failures: list[str]) -> str:
    if not failures:
        return "pass"
    if expected in {"高质量", "高质量样本"}:
        return "false_negative"
    if expected in {"高风险", "高风险样本", "争议成长", "争议样本", "争议"}:
        return "false_positive"
    return "unknown"


def evaluate_case(
    calibration_row: dict[str, str],
    screening_row: dict[str, str] | None,
    pool_row: dict[str, str] | None,
) -> dict[str, str]:
    expected = (calibration_row.get("预期类别") or "").strip()
    allowed_results = split_cell(calibration_row.get("允许结果"))
    forbidden_levels = split_cell(calibration_row.get("禁止优质池等级"))
    min_level = (calibration_row.get("最低优质池等级") or "").strip()

    current_result = normalize_result(screening_row.get("结果") if screening_row else "缺失")
    pool_level = (pool_row.get("优质池等级") if pool_row else "未入池") or "未入池"
    ai_rating = get_ai_rating(screening_row)
    failures: list[str] = []

    if screening_row is None:
        failures.append("筛选结果缺失")

    if expected in {"高质量", "高质量样本"}:
        if screening_row is not None:
            if allowed_results and current_result not in allowed_results:
                failures.append(f"当前结果为{current_result}，不在允许结果内")
            elif not allowed_results and current_result in BAD_HIGH_QUALITY_RESULTS:
                failures.append(f"高质量样本被判为{current_result}")
            if ai_rating in NEGATIVE_AI_RATINGS:
                failures.append(f"AI评级为{ai_rating}")
        if min_level and pool_rank(pool_level) < pool_rank(min_level):
            failures.append(f"优质池等级{pool_level}低于最低预期{min_level}")
    elif expected in {"高风险", "高风险样本"}:
        if screening_row is not None:
            if allowed_results and current_result not in allowed_results:
                failures.append(f"当前结果为{current_result}，不在允许结果内")
            elif not allowed_results and current_result == "通过":
                failures.append("高风险样本被规则通过")
            if ai_rating in POSITIVE_AI_RATINGS:
                failures.append(f"高风险样本AI评级偏正面：{ai_rating}")
        blocked_levels = forbidden_levels or {"核心优质池", "优质池"}
        if pool_level in blocked_levels:
            failures.append(f"高风险样本进入{pool_level}")
    elif expected in {"争议成长", "争议样本", "争议"}:
        if screening_row is not None and allowed_results and current_result not in allowed_results:
            failures.append(f"当前结果为{current_result}，不在允许结果内")
        blocked_levels = forbidden_levels or {"核心优质池"}
        if pool_level in blocked_levels:
            failures.append(f"争议样本进入{pool_level}")
    else:
        failures.append(f"未知预期类别：{expected or '-'}")

    name = calibration_row.get("名称") or (screening_row or {}).get("名称") or (pool_row or {}).get("名称") or ""
    return {
        "股票": calibration_row.get("股票", ""),
        "市场": calibration_row.get("市场", ""),
        "名称": name,
        "预期类别": expected,
        "校准通过": "否" if failures else "是",
        "错误类型": error_type_for(expected, failures),
        "失败原因": "；".join(failures) if failures else "-",
        "当前结果": current_result,
        "规则质量评级": (screening_row or {}).get("规则质量评级", ""),
        "规则质量分": (screening_row or {}).get("规则质量分", ""),
        "AI评级": ai_rating or "-",
        "数据年数": (screening_row or {}).get("数据年数", ""),
        "数据质量分": (screening_row or {}).get("数据质量分", ""),
        "数据质量": (screening_row or {}).get("数据质量", ""),
        "综合优质分": (pool_row or {}).get("综合优质分", ""),
        "优质池等级": pool_level,
        "入选来源": (pool_row or {}).get("入选来源", ""),
        "风险扣分": (pool_row or {}).get("风险扣分", ""),
        "综合观察": (screening_row or {}).get("综合观察", ""),
        "校准说明": calibration_row.get("说明", ""),
    }


def evaluate_all(
    calibration_rows: list[dict[str, str]],
    screening_rows: list[dict[str, str]],
    quality_pool_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    screening_index = index_by_stock(screening_rows)
    pool_index = index_by_stock(quality_pool_rows)
    return [
        evaluate_case(row, screening_index.get(stock_key(row)), pool_index.get(stock_key(row)))
        for row in calibration_rows
    ]


def main() -> None:
    args = parse_args()
    report_rows = evaluate_all(
        read_rows(args.calibration),
        read_rows(args.screening),
        read_rows(args.quality_pool),
    )
    write_rows(args.output, report_rows)

    passed = sum(1 for row in report_rows if row["校准通过"] == "是")
    total = len(report_rows)
    print(f"Calibration passed {passed}/{total}; failures {total - passed}; report: {args.output}")
    error_counts: dict[str, int] = {}
    for row in report_rows:
        error_counts[row["错误类型"]] = error_counts.get(row["错误类型"], 0) + 1
    print(
        "Error types: "
        + ", ".join(f"{error_type}={count}" for error_type, count in sorted(error_counts.items()))
    )
    for row in report_rows:
        if row["校准通过"] != "是":
            print(f"- {row['市场']} {row['股票']} {row['名称']}: {row['失败原因']}")


if __name__ == "__main__":
    main()
