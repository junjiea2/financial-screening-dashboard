"""Industry classification and profile-specific screening hints."""

from __future__ import annotations

from dataclasses import dataclass

from models import FinancialRecord, StockFinancials


@dataclass(frozen=True, slots=True)
class IndustryProfile:
    code: str
    label: str
    core_metrics: tuple[str, ...]


PROFILES = {
    "bank": IndustryProfile("bank", "银行", ("不良率", "拨备覆盖", "资本充足率")),
    "insurance": IndustryProfile("insurance", "保险", ("偿付能力", "久期缺口", "投资收益质量")),
    "real_estate": IndustryProfile("real_estate", "地产", ("净负债率", "现金短债比", "资产负债率")),
    "technology": IndustryProfile("technology", "科技", ("营收增长", "自由现金流", "研发投入效率")),
    "consumer": IndustryProfile("consumer", "消费", ("ROE", "毛利率稳定性", "分红稳定性")),
    "cyclical": IndustryProfile("cyclical", "周期", ("利润波动", "ROE波动", "资本开支周期")),
    "financial": IndustryProfile("financial", "金融", ("杠杆", "资产质量", "资本约束")),
    "general": IndustryProfile("general", "通用", ("ROE", "现金流", "资产负债率")),
}


KEYWORDS = {
    "bank": ("bank", "banks", "银行"),
    "insurance": ("insurance", "保险"),
    "real_estate": ("real estate", "reit", "房地产", "地产"),
    "technology": (
        "technology",
        "software",
        "semiconductor",
        "internet",
        "computer",
        "electronic",
        "科技",
        "软件",
        "半导体",
        "互联网",
        "电子",
        "通信",
    ),
    "consumer": (
        "consumer",
        "beverage",
        "food",
        "retail",
        "apparel",
        "household",
        "消费",
        "食品",
        "饮料",
        "零售",
        "家电",
        "服饰",
    ),
    "cyclical": (
        "materials",
        "energy",
        "steel",
        "chemical",
        "mining",
        "coal",
        "oil",
        "shipping",
        "construction",
        "basic materials",
        "周期",
        "材料",
        "钢铁",
        "煤炭",
        "石油",
        "化工",
        "有色",
        "航运",
        "建筑",
    ),
    "financial": ("brokerage", "capital markets", "financial services", "券商", "金融"),
}


def classify_industry(stock: StockFinancials) -> IndustryProfile:
    text = " ".join(
        value.lower()
        for value in (stock.industry, stock.name, stock.symbol)
        if value
    )
    for profile_code, keywords in KEYWORDS.items():
        if any(keyword.lower() in text for keyword in keywords):
            return PROFILES[profile_code]
    return PROFILES["general"]


def latest_record(records: list[FinancialRecord]) -> FinancialRecord | None:
    if not records:
        return None
    return max(records, key=lambda item: item.year)


def apply_industry_rules(
    stock: StockFinancials,
    profile: IndustryProfile,
    metrics: dict[str, float | int | str | None],
) -> tuple[int, int, list[str], bool]:
    """Return exclusions, warnings, flags, and whether generic pass is blocked."""
    flags: list[str] = []
    exclusions = 0
    warnings = 0
    blocks_generic_pass = False
    latest = latest_record(stock.records)

    if profile.code == "bank":
        blocks_generic_pass = True
        npl = latest.non_performing_loan_ratio if latest else None
        if npl is None:
            warnings += 1
            flags.append("银行需补充不良率/拨备/资本充足率专项数据")
        elif npl > 0.03:
            exclusions += 1
            flags.append("银行不良率过高")
        elif npl > 0.015:
            warnings += 1
            flags.append("银行不良率偏高")

    elif profile.code == "insurance":
        blocks_generic_pass = True
        solvency = latest.solvency_ratio if latest else None
        duration_gap = latest.duration_gap if latest else None
        if solvency is None or duration_gap is None:
            warnings += 1
            flags.append("保险需补充偿付能力/久期缺口专项数据")
        elif solvency < 1.5 or abs(duration_gap) > 3:
            warnings += 1
            flags.append("保险偿付能力或久期匹配需警惕")

    elif profile.code == "real_estate":
        blocks_generic_pass = True
        net_gearing = latest.net_gearing_ratio if latest else None
        asset_liability = metrics.get("asset_liability_ratio")
        if net_gearing is None:
            warnings += 1
            flags.append("地产需补充净负债率/现金短债比专项数据")
        elif net_gearing > 1:
            exclusions += 1
            flags.append("地产净负债率过高")
        if isinstance(asset_liability, float) and asset_liability > 0.75:
            warnings += 1
            flags.append("地产资产负债率偏高")

    elif profile.code == "technology":
        revenue_cagr = metrics.get("revenue_cagr_5y")
        avg_fcf = metrics.get("avg_free_cash_flow_5y")
        if isinstance(revenue_cagr, float) and revenue_cagr < 0:
            warnings += 1
            flags.append("科技公司营收增长转负")
        if isinstance(avg_fcf, float) and avg_fcf < 0:
            warnings += 1
            flags.append("科技公司自由现金流为负")

    elif profile.code == "consumer":
        avg_roe = metrics.get("avg_roe_10y")
        dividend_status = metrics.get("dividend_status")
        if isinstance(avg_roe, float) and avg_roe < 0.10:
            warnings += 1
            flags.append("消费公司长期ROE不够突出")
        if dividend_status in {"不连续", "有明显下滑"}:
            warnings += 1
            flags.append("消费公司分红稳定性不足")

    elif profile.code == "cyclical":
        roe_volatility = metrics.get("roe_volatility_10y")
        net_income_cv = metrics.get("net_income_cv_10y")
        if isinstance(roe_volatility, float) and roe_volatility > 0.15:
            warnings += 1
            flags.append("周期行业ROE波动显著")
        if isinstance(net_income_cv, float) and net_income_cv > 1:
            warnings += 1
            flags.append("周期行业利润弹性过大")

    elif profile.code == "financial":
        blocks_generic_pass = True
        warnings += 1
        flags.append("金融行业需专项资产质量与资本约束分析")

    return exclusions, warnings, flags, blocks_generic_pass

