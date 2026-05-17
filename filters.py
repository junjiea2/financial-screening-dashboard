"""Four-step financial minefield screening rules."""

from __future__ import annotations

from config import DEFAULT_THRESHOLDS, HIGH_LEVERAGE_INDUSTRIES
from data_quality import score_data_quality
from industry_model import apply_industry_rules, classify_industry
from indicators import (
    coefficient_of_variation,
    count_negative,
    dividend_stability,
    free_cash_flow,
    infer_roe,
    latest_asset_liability_ratio,
    last_n_records,
    latest_debt_to_equity,
    latest_goodwill_ratio,
    latest_interest_coverage,
    revenue_cagr,
    safe_mean,
    sample_std,
)
from models import ScreeningResult, StockFinancials


QUALITY_PROFILES = {
    "consumer": {
        "roe_good": 0.15,
        "roe_min": 0.10,
        "roe_vol_max": 0.10,
        "debt_warn": 0.60,
        "growth_good": 0.05,
        "growth_min": 0.02,
        "allow_cycle": False,
    },
    "technology": {
        "roe_good": 0.12,
        "roe_min": 0.06,
        "roe_vol_max": 0.14,
        "debt_warn": 0.50,
        "growth_good": 0.08,
        "growth_min": 0.03,
        "allow_cycle": False,
    },
    "bank": {
        "roe_good": 0.08,
        "roe_min": 0.05,
        "roe_vol_max": 0.08,
        "debt_warn": None,
        "growth_good": 0.02,
        "growth_min": -0.02,
        "allow_cycle": False,
    },
    "cyclical": {
        "roe_good": 0.10,
        "roe_min": 0.04,
        "roe_vol_max": 0.18,
        "debt_warn": 0.70,
        "growth_good": 0.05,
        "growth_min": -0.05,
        "allow_cycle": True,
    },
    "real_estate": {
        "roe_good": 0.10,
        "roe_min": 0.05,
        "roe_vol_max": 0.15,
        "debt_warn": None,
        "growth_good": 0.03,
        "growth_min": -0.05,
        "allow_cycle": True,
    },
    "financial": {
        "roe_good": 0.08,
        "roe_min": 0.05,
        "roe_vol_max": 0.10,
        "debt_warn": None,
        "growth_good": 0.02,
        "growth_min": -0.02,
        "allow_cycle": False,
    },
    "insurance": {
        "roe_good": 0.08,
        "roe_min": 0.05,
        "roe_vol_max": 0.12,
        "debt_warn": None,
        "growth_good": 0.02,
        "growth_min": -0.02,
        "allow_cycle": False,
    },
    "general": {
        "roe_good": 0.12,
        "roe_min": 0.07,
        "roe_vol_max": 0.12,
        "debt_warn": 0.65,
        "growth_good": 0.03,
        "growth_min": 0.00,
        "allow_cycle": False,
    },
}


def _quality_rating(score: int) -> str:
    if score >= 88:
        return "优质候选"
    if score >= 65:
        return "可跟踪"
    if score >= 45:
        return "谨慎观察"
    return "排除"


def rate_rule_quality(
    stock: StockFinancials,
    profile_code: str,
    mine_result: str,
    data_years: int,
    data_quality_level: str,
    avg_roe_10y: float | None,
    roe_volatility_10y: float | None,
    net_income_cv_10y: float | None,
    five_year_loss_count: int,
    five_year_negative_ocf_count: int,
    five_year_negative_fcf_count: int,
    avg_free_cash_flow_5y: float | None,
    asset_liability_ratio: float | None,
    revenue_cagr_5y: float | None,
) -> tuple[str, int, list[str]]:
    if mine_result == "数据不足" or data_quality_level in {"Low", "Insufficient"}:
        return "数据不足", 0, ["数据不足，不能进行质量评级"]
    if mine_result == "排除":
        return "排除", 20, ["规则排雷已判定存在硬伤"]
    if mine_result == "需专项分析":
        return "需专项分析", 45, ["行业需要专项资产质量或资本约束分析"]

    rules = QUALITY_PROFILES.get(profile_code, QUALITY_PROFILES["general"])
    score = 45
    flags: list[str] = []

    if data_quality_level == "High":
        score += 5
        flags.append("数据质量高")
    elif data_quality_level == "Medium":
        flags.append("数据质量中等，质量评级需降置信度")

    roe_good = rules["roe_good"]
    roe_min = rules["roe_min"]
    if avg_roe_10y is None:
        score -= 12
        flags.append("长期ROE缺失")
    elif avg_roe_10y >= roe_good:
        score += 22
        flags.append("长期ROE达到行业优秀线")
    elif avg_roe_10y >= roe_min:
        score += 8
        flags.append("长期ROE达到行业基本线")
    else:
        score -= 10
        flags.append("长期ROE低于行业基本线")

    roe_vol_max = rules["roe_vol_max"]
    if roe_volatility_10y is not None:
        if roe_volatility_10y <= roe_vol_max:
            score += 8
            flags.append("ROE稳定性较好")
        elif avg_roe_10y is not None and avg_roe_10y < roe_min:
            score -= 18
            flags.append("ROE不高且波动较大")
        elif not rules["allow_cycle"]:
            score -= 6
            flags.append("ROE波动偏大")

    if net_income_cv_10y is not None and net_income_cv_10y > 1.2 and not rules["allow_cycle"]:
        score -= 8
        flags.append("净利润波动偏大")

    if five_year_loss_count == 0:
        score += 6
        flags.append("近5年无亏损")
    elif profile_code == "technology" and five_year_loss_count <= 2:
        score -= 4
        flags.append("科技/成长公司有亏损记录，需看亏损是否收窄")
    else:
        score -= 15
        flags.append("近5年出现亏损")

    if five_year_negative_ocf_count == 0:
        score += 12
        flags.append("近5年经营现金流持续为正")
    elif five_year_negative_ocf_count >= 3:
        score -= 25
        flags.append("经营现金流多次为负")
    else:
        score -= 8
        flags.append("经营现金流存在瑕疵")

    if avg_free_cash_flow_5y is None:
        score -= 5
        flags.append("自由现金流数据缺失，评级保守")
    elif avg_free_cash_flow_5y > 0 and five_year_negative_fcf_count < 3:
        score += 6
        flags.append("自由现金流整体为正")
    else:
        score -= 10
        flags.append("自由现金流质量不足")

    debt_warn = rules["debt_warn"]
    if debt_warn is not None and asset_liability_ratio is not None:
        if asset_liability_ratio <= debt_warn:
            score += 4
            flags.append("资产负债率符合行业语境")
        elif asset_liability_ratio <= debt_warn + 0.08:
            score -= 4
            flags.append("资产负债率略高但未构成硬伤")
        else:
            score -= 12
            flags.append("资产负债率高于行业舒适区")

    growth_good = rules["growth_good"]
    growth_min = rules["growth_min"]
    if revenue_cagr_5y is None:
        flags.append("营收增长数据不足")
    elif revenue_cagr_5y >= growth_good:
        score += 6
        flags.append("营收增长达到行业较好水平")
    elif revenue_cagr_5y >= growth_min:
        flags.append("营收增长处于可接受区间")
    elif rules["allow_cycle"]:
        score -= 4
        flags.append("周期行业营收下滑，需结合行业周期位置")
    else:
        score -= 10
        flags.append("营收增长偏弱")

    score = max(0, min(100, score))
    return _quality_rating(score), score, flags


def screen_stock(
    stock: StockFinancials,
    thresholds: dict[str, float | int] | None = None,
) -> ScreeningResult:
    limits = DEFAULT_THRESHOLDS | (thresholds or {})
    flags: list[str] = []
    exclusions = 0
    warnings = 0
    profile = classify_industry(stock)
    data_years, missing_count, data_quality_score, data_quality_level = (
        score_data_quality(stock.records, stock.market)
    )

    five_year = last_n_records(stock.records, 5)
    ten_year = last_n_records(stock.records, 10)
    ten_year_roe = [infer_roe(record) for record in ten_year]
    five_year_net_income = [record.net_income for record in five_year]
    ten_year_net_income = [record.net_income for record in ten_year]
    five_year_ocf = [record.operating_cash_flow for record in five_year]
    five_year_fcf = [free_cash_flow(record) for record in five_year]

    avg_roe_10y = safe_mean(ten_year_roe)
    roe_volatility_10y = sample_std(ten_year_roe)
    net_income_cv_10y = coefficient_of_variation(ten_year_net_income)
    five_year_loss_count = count_negative(five_year_net_income)
    ten_year_loss_count = count_negative(ten_year_net_income)
    five_year_negative_ocf_count = count_negative(five_year_ocf)
    five_year_negative_fcf_count = count_negative(five_year_fcf)
    debt_to_equity = latest_debt_to_equity(stock.records)
    avg_free_cash_flow_5y = safe_mean(five_year_fcf)
    asset_liability_ratio = latest_asset_liability_ratio(stock.records)
    goodwill_ratio = latest_goodwill_ratio(stock.records)
    interest_coverage = latest_interest_coverage(stock.records)
    revenue_cagr_5y = revenue_cagr(stock.records, 5)
    dividend_status, dividend_warning = dividend_stability(stock.records, 5)
    industry = stock.industry or ""
    is_high_leverage_industry = industry in HIGH_LEVERAGE_INDUSTRIES
    industry_metrics = {
        "avg_roe_10y": avg_roe_10y,
        "roe_volatility_10y": roe_volatility_10y,
        "net_income_cv_10y": net_income_cv_10y,
        "avg_free_cash_flow_5y": avg_free_cash_flow_5y,
        "asset_liability_ratio": asset_liability_ratio,
        "revenue_cagr_5y": revenue_cagr_5y,
        "dividend_status": dividend_status,
    }
    industry_exclusions, industry_warnings, industry_flags, block_generic_pass = (
        apply_industry_rules(stock, profile, industry_metrics)
    )
    exclusions += industry_exclusions
    warnings += industry_warnings
    flags.extend(industry_flags)

    if stock.pb is not None and stock.pb < limits["low_pb"]:
        if five_year_loss_count >= limits["five_year_loss_count_exclude"]:
            exclusions += 1
            flags.append("PB低但近5年出现亏损")
        if five_year_negative_ocf_count >= limits["five_year_negative_ocf_count_exclude"]:
            exclusions += 1
            flags.append("PB低但近5年经营现金流多次为负")

    if ten_year_loss_count >= limits["ten_year_loss_count_exclude"]:
        exclusions += 1
        flags.append("10年内亏损年份过多")

    if roe_volatility_10y is not None and roe_volatility_10y > limits["roe_volatility_warn"]:
        warnings += 1
        flags.append("10年ROE波动较大")

    if net_income_cv_10y is not None and net_income_cv_10y > limits["net_income_cv_warn"]:
        warnings += 1
        flags.append("10年净利润波动较大")

    if avg_roe_10y is not None and avg_roe_10y < limits["avg_roe_very_low"]:
        exclusions += 1
        flags.append("长期ROE低于5%")
    elif (
        avg_roe_10y is not None
        and avg_roe_10y < limits["avg_roe_low"]
        and stock.pe is not None
        and stock.pe > limits["pe_low_return_trap"]
    ):
        warnings += 1
        flags.append("长期ROE偏低但PE不低")

    if five_year_negative_fcf_count >= limits["five_year_negative_fcf_count_warn"]:
        warnings += 1
        flags.append("近5年自由现金流多次为负")

    if (
        asset_liability_ratio is not None
        and asset_liability_ratio > limits["asset_liability_ratio_exclude"]
        and not is_high_leverage_industry
    ):
        exclusions += 1
        flags.append("资产负债率过高")
    elif (
        asset_liability_ratio is not None
        and asset_liability_ratio > limits["asset_liability_ratio_warn"]
        and not is_high_leverage_industry
    ):
        warnings += 1
        flags.append("资产负债率偏高")

    if goodwill_ratio is not None and goodwill_ratio > limits["goodwill_ratio_exclude"]:
        exclusions += 1
        flags.append("商誉占比过高")
    elif goodwill_ratio is not None and goodwill_ratio > limits["goodwill_ratio_warn"]:
        warnings += 1
        flags.append("商誉占比偏高")

    if (
        interest_coverage is not None
        and interest_coverage < limits["interest_coverage_exclude"]
    ):
        exclusions += 1
        flags.append("利息覆盖倍数过低")
    elif (
        interest_coverage is not None
        and interest_coverage < limits["interest_coverage_warn"]
    ):
        warnings += 1
        flags.append("利息覆盖倍数偏低")

    if revenue_cagr_5y is not None and revenue_cagr_5y < limits["revenue_cagr_exclude"]:
        exclusions += 1
        flags.append("近5年营收明显下滑")
    elif revenue_cagr_5y is not None and revenue_cagr_5y < limits["revenue_cagr_warn"]:
        warnings += 1
        flags.append("近5年营收增长偏弱")

    if dividend_warning:
        warnings += dividend_warning
        flags.append(f"分红稳定性：{dividend_status}")

    if is_high_leverage_industry:
        warnings += 2
        flags.append("高杠杆行业，需资产负债表专项分析")

    leverage_risk = "未知"
    if is_high_leverage_industry:
        leverage_risk = "高"
    elif debt_to_equity is not None and debt_to_equity > limits["debt_to_equity_warn"]:
        leverage_risk = "中"
        warnings += 1
        flags.append("资产负债率相对偏高")
    elif debt_to_equity is not None:
        leverage_risk = "低"

    score = max(0, 100 - exclusions * 40 - warnings * 15)
    if data_quality_level in {"Low", "Insufficient"}:
        result = "数据不足"
        score = 0
        flags.append("数据年数不足，无法进行可靠筛选")
    elif exclusions > 0:
        result = "排除"
    elif is_high_leverage_industry or block_generic_pass:
        result = "需专项分析"
    elif warnings > 0:
        result = "警惕"
    else:
        result = "通过"

    if data_quality_level == "Medium":
        score = min(score, 85)
        flags.append("数据质量为Medium，筛选结果置信度中等")

    rule_quality_rating, rule_quality_score, quality_flags = rate_rule_quality(
        stock=stock,
        profile_code=profile.code,
        mine_result=result,
        data_years=data_years,
        data_quality_level=data_quality_level,
        avg_roe_10y=avg_roe_10y,
        roe_volatility_10y=roe_volatility_10y,
        net_income_cv_10y=net_income_cv_10y,
        five_year_loss_count=five_year_loss_count,
        five_year_negative_ocf_count=five_year_negative_ocf_count,
        five_year_negative_fcf_count=five_year_negative_fcf_count,
        avg_free_cash_flow_5y=avg_free_cash_flow_5y,
        asset_liability_ratio=asset_liability_ratio,
        revenue_cagr_5y=revenue_cagr_5y,
    )

    return ScreeningResult(
        symbol=stock.symbol,
        market=stock.market,
        name=stock.name,
        industry=stock.industry,
        pe=stock.pe,
        pb=stock.pb,
        avg_roe_10y=avg_roe_10y,
        roe_volatility_10y=roe_volatility_10y,
        debt_to_equity_latest=debt_to_equity,
        avg_free_cash_flow_5y=avg_free_cash_flow_5y,
        asset_liability_ratio_latest=asset_liability_ratio,
        goodwill_ratio_latest=goodwill_ratio,
        interest_coverage_latest=interest_coverage,
        dividend_stability=dividend_status,
        revenue_cagr_5y=revenue_cagr_5y,
        data_years=data_years,
        missing_field_count=missing_count,
        data_quality_score=data_quality_score,
        data_quality_level=data_quality_level,
        industry_profile=profile.label,
        core_metrics="、".join(profile.core_metrics),
        leverage_risk=leverage_risk,
        result=result,
        score=score,
        flags=flags,
        rule_quality_rating=rule_quality_rating,
        rule_quality_score=rule_quality_score,
        quality_flags=quality_flags,
        metrics={
            "five_year_loss_count": five_year_loss_count,
            "ten_year_loss_count": ten_year_loss_count,
            "five_year_negative_ocf_count": five_year_negative_ocf_count,
            "five_year_negative_fcf_count": five_year_negative_fcf_count,
            "net_income_cv_10y": net_income_cv_10y,
        },
    )


def screen_universe(stocks: list[StockFinancials]) -> list[ScreeningResult]:
    return [screen_stock(stock) for stock in stocks]
