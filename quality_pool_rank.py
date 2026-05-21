"""Rank higher-quality stocks from any rule/AI positive signal."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


OUTPUT_COLUMNS = [
    "综合优质分",
    "优质池等级",
    "入选来源",
    "优质排序理由",
    "风险扣分",
]

POSITIVE_RULE_QUALITY = {"优质候选", "可跟踪"}
POSITIVE_AI_RATINGS = {"优质候选", "可跟踪", "通过复核", "谨慎通过"}
SPECIAL_INDUSTRIES = {"银行", "金融", "保险", "地产"}
AI_RATING_SCORE = {
    "优质候选": 100,
    "通过复核": 92,
    "可跟踪": 76,
    "谨慎通过": 68,
    "谨慎观察": 45,
    "转为警惕": 35,
    "建议排除": 10,
    "排除": 0,
    "数据不足": 0,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rank quality pool from dual-track results.")
    parser.add_argument("--input", required=True, help="Dual-track or rule screening CSV.")
    parser.add_argument("--output", required=True, help="Quality pool ranking CSV.")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--include-excluded", action="store_true", help="Keep rule-excluded AI positives as high-disagreement cases.")
    return parser.parse_args()


def read_rows(path: str | Path) -> tuple[list[str], list[dict[str, str]]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_rows(path: str | Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def number(value: str | None, default: float = 0) -> float:
    if value is None:
        return default
    text = str(value).replace("%", "").replace(",", "").strip()
    if text in {"", "-"}:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def bounded(value: float) -> float:
    return max(0, min(100, value))


def score_roe(row: dict[str, str]) -> float:
    roe = number(row.get("10年ROE"), default=-999)
    if roe == -999:
        return 45
    if roe >= 20:
        return 100
    if roe >= 15:
        return 90
    if roe >= 10:
        return 72
    if roe >= 5:
        return 45
    return 10


def score_stability(row: dict[str, str]) -> float:
    volatility = number(row.get("ROE波动"), default=-1)
    if volatility < 0:
        return 50
    if volatility <= 5:
        return 100
    if volatility <= 10:
        return 82
    if volatility <= 15:
        return 62
    if volatility <= 25:
        return 35
    return 12


def score_cashflow(row: dict[str, str]) -> float:
    fcf = number(row.get("5年平均FCF"), default=0)
    if row.get("5年平均FCF") in {"", "-", None}:
        return 48
    return 86 if fcf > 0 else 18


def score_debt(row: dict[str, str]) -> float:
    if row.get("行业模型") in SPECIAL_INDUSTRIES:
        return 55
    debt = number(row.get("资产负债率"), default=-1)
    if debt < 0:
        return 50
    if debt <= 30:
        return 100
    if debt <= 50:
        return 82
    if debt <= 65:
        return 58
    if debt <= 80:
        return 28
    return 8


def score_growth(row: dict[str, str]) -> float:
    growth = number(row.get("5年营收CAGR"), default=-999)
    if growth == -999:
        return 50
    if growth >= 10:
        return 100
    if growth >= 5:
        return 82
    if growth >= 0:
        return 60
    if growth >= -5:
        return 35
    return 10


def score_valuation(row: dict[str, str]) -> float:
    pe = number(row.get("PE"), default=0)
    pb = number(row.get("PB"), default=0)
    pe_score = 50
    if pe > 0:
        if pe <= 15:
            pe_score = 92
        elif pe <= 25:
            pe_score = 76
        elif pe <= 40:
            pe_score = 52
        elif pe <= 70:
            pe_score = 28
        else:
            pe_score = 10
    pb_score = 50
    if pb > 0:
        if pb <= 2:
            pb_score = 86
        elif pb <= 5:
            pb_score = 65
        elif pb <= 10:
            pb_score = 36
        else:
            pb_score = 14
    return pe_score * 0.65 + pb_score * 0.35


def entry_sources(row: dict[str, str]) -> list[str]:
    sources = []
    if row.get("结果") == "通过":
        sources.append("规则通过")
    if row.get("规则质量评级") in POSITIVE_RULE_QUALITY:
        sources.append(f"规则质量{row.get('规则质量评级')}")
    ai_rating = row.get("AI评级") or row.get("AI判断")
    if ai_rating in POSITIVE_AI_RATINGS:
        sources.append(f"AI{ai_rating}")
    return sources


def rank_row(row: dict[str, str], include_excluded: bool = False) -> dict[str, str] | None:
    sources = entry_sources(row)
    if not sources:
        return None
    if row.get("结果") in {"数据不足", "需专项分析"}:
        return None
    ai_positive = any(source.startswith("AI") for source in sources)
    if row.get("结果") == "排除" and not (include_excluded and ai_positive):
        return None

    rule_quality = number(row.get("规则质量分"), default=0)
    rule_screen = number(row.get("分数"), default=0)
    data_quality = number(row.get("数据质量分"), default=0)
    ai_rating = row.get("AI评级") or row.get("AI判断") or ""
    ai_score = AI_RATING_SCORE.get(ai_rating, 52 if not ai_rating else 35)

    component_score = (
        rule_quality * 0.30
        + ai_score * 0.15
        + rule_screen * 0.10
        + data_quality * 0.10
        + score_roe(row) * 0.12
        + score_stability(row) * 0.08
        + score_cashflow(row) * 0.06
        + score_debt(row) * 0.04
        + score_growth(row) * 0.03
        + score_valuation(row) * 0.02
    )

    penalties: list[str] = []
    data_years = number(row.get("数据年数"), default=0)
    if data_years and data_years < 5:
        component_score = min(component_score, 78)
        penalties.append("短历史封顶")
    if row.get("结果") == "警惕":
        component_score -= 4
        penalties.append("排雷需关注")
    if row.get("结果") == "排除":
        component_score = min(component_score - 12, 68)
        penalties.append("规则排除高争议")
    if row.get("规则AI分歧") == "是":
        component_score -= 3
        penalties.append("规则AI分歧")

    score = round(bounded(component_score), 1)
    if row.get("结果") == "排除" and ai_positive:
        level = "高争议池"
    elif score >= 88:
        level = "核心优质池"
    elif score >= 78:
        level = "优质池"
    elif score >= 68:
        level = "可研究池"
    else:
        level = "观察池"

    reasons = [
        f"规则质量{row.get('规则质量分', '-')}",
        f"ROE{row.get('10年ROE', '-')}",
        f"ROE波动{row.get('ROE波动', '-')}",
        f"数据质量{row.get('数据质量', '-')}",
    ]
    if ai_rating:
        reasons.append(f"AI{ai_rating}")
    if row.get("PE") not in {"", "-"}:
        reasons.append(f"PE{row.get('PE')}")
    if row.get("PB") not in {"", "-"}:
        reasons.append(f"PB{row.get('PB')}")

    output = dict(row)
    output.update(
        {
            "综合优质分": f"{score:.1f}",
            "优质池等级": level,
            "入选来源": "；".join(sources),
            "优质排序理由": "；".join(reasons),
            "风险扣分": "；".join(penalties) if penalties else "-",
        }
    )
    return output


def build_quality_pool(
    rows: list[dict[str, str]],
    include_excluded: bool = False,
) -> list[dict[str, str]]:
    ranked = [
        ranked_row
        for row in rows
        if (ranked_row := rank_row(row, include_excluded=include_excluded)) is not None
    ]
    ranked.sort(
        key=lambda row: (
            number(row.get("综合优质分"), default=0),
            number(row.get("规则质量分"), default=0),
            number(row.get("数据质量分"), default=0),
        ),
        reverse=True,
    )
    return ranked


def main() -> None:
    args = parse_args()
    headers, rows = read_rows(args.input)
    ranked = build_quality_pool(rows, include_excluded=args.include_excluded)
    if args.limit:
        ranked = ranked[: args.limit]
    output_headers = OUTPUT_COLUMNS + [header for header in headers if header not in OUTPUT_COLUMNS]
    write_rows(args.output, output_headers, ranked)
    print(f"Wrote {len(ranked)} quality pool rows to {args.output}")


if __name__ == "__main__":
    main()
