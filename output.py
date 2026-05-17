"""Output formatting for screening results."""

from __future__ import annotations

import csv
from pathlib import Path

from models import ScreeningResult


HEADERS = [
    "股票",
    "市场",
    "名称",
    "行业",
    "行业模型",
    "核心指标",
    "PE",
    "PB",
    "10年ROE",
    "ROE波动",
    "5年平均FCF",
    "资产负债率",
    "商誉占比",
    "利息覆盖倍数",
    "分红稳定性",
    "5年营收CAGR",
    "数据年数",
    "缺失字段数",
    "数据质量分",
    "数据质量",
    "杠杆风险",
    "结果",
    "分数",
    "规则质量评级",
    "规则质量分",
    "质量理由",
    "原因",
]


def format_percent(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value * 100:.1f}%"


def format_number(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}"


def result_to_row(result: ScreeningResult) -> list[str]:
    return [
        result.symbol,
        result.market,
        result.name or "-",
        result.industry or "-",
        result.industry_profile,
        result.core_metrics,
        format_number(result.pe),
        format_number(result.pb),
        format_percent(result.avg_roe_10y),
        format_percent(result.roe_volatility_10y),
        format_number(result.avg_free_cash_flow_5y),
        format_percent(result.asset_liability_ratio_latest),
        format_percent(result.goodwill_ratio_latest),
        format_number(result.interest_coverage_latest),
        result.dividend_stability,
        format_percent(result.revenue_cagr_5y),
        str(result.data_years),
        str(result.missing_field_count),
        str(result.data_quality_score),
        result.data_quality_level,
        result.leverage_risk,
        result.result,
        str(result.score),
        result.rule_quality_rating,
        str(result.rule_quality_score),
        "；".join(result.quality_flags) if result.quality_flags else "-",
        "；".join(result.flags) if result.flags else "-",
    ]


def print_table(results: list[ScreeningResult]) -> None:
    rows = [result_to_row(result) for result in results]
    widths = [
        max(len(str(value)) for value in column)
        for column in zip(HEADERS, *rows, strict=False)
    ]
    header = "  ".join(value.ljust(width) for value, width in zip(HEADERS, widths))
    print(header)
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(value.ljust(width) for value, width in zip(row, widths)))


def write_csv(results: list[ScreeningResult], path: str | Path) -> None:
    with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADERS)
        writer.writerows(result_to_row(result) for result in results)
