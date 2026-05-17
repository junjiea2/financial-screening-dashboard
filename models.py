"""Domain models used by the screener."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class FinancialRecord:
    year: int
    revenue: float | None = None
    net_income: float | None = None
    operating_cash_flow: float | None = None
    shareholders_equity: float | None = None
    total_assets: float | None = None
    total_liabilities: float | None = None
    asset_liability_ratio: float | None = None
    capital_expenditure: float | None = None
    free_cash_flow: float | None = None
    goodwill: float | None = None
    ebit: float | None = None
    interest_expense: float | None = None
    dividends_paid: float | None = None
    non_performing_loan_ratio: float | None = None
    solvency_ratio: float | None = None
    duration_gap: float | None = None
    net_gearing_ratio: float | None = None
    roe: float | None = None


@dataclass(slots=True)
class StockFinancials:
    symbol: str
    market: str
    name: str | None = None
    industry: str | None = None
    pe: float | None = None
    pb: float | None = None
    records: list[FinancialRecord] = field(default_factory=list)
    source: str = "manual"


@dataclass(slots=True)
class ScreeningResult:
    symbol: str
    market: str
    name: str | None
    industry: str | None
    pe: float | None
    pb: float | None
    avg_roe_10y: float | None
    roe_volatility_10y: float | None
    debt_to_equity_latest: float | None
    avg_free_cash_flow_5y: float | None
    asset_liability_ratio_latest: float | None
    goodwill_ratio_latest: float | None
    interest_coverage_latest: float | None
    dividend_stability: str
    revenue_cagr_5y: float | None
    data_years: int
    missing_field_count: int
    data_quality_score: int
    data_quality_level: str
    industry_profile: str
    core_metrics: str
    leverage_risk: str
    result: str
    score: int
    flags: list[str]
    rule_quality_rating: str = "未评级"
    rule_quality_score: int = 0
    quality_flags: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
