"""Financial indicator helpers."""

from __future__ import annotations

from math import sqrt
from statistics import mean

from models import FinancialRecord


def last_n_records(records: list[FinancialRecord], years: int) -> list[FinancialRecord]:
    return sorted(records, key=lambda item: item.year, reverse=True)[:years]


def safe_mean(values: list[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    if not clean:
        return None
    return mean(clean)


def sample_std(values: list[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    if len(clean) < 2:
        return None
    avg = mean(clean)
    return sqrt(sum((value - avg) ** 2 for value in clean) / (len(clean) - 1))


def coefficient_of_variation(values: list[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    if len(clean) < 2:
        return None
    avg = mean(clean)
    if abs(avg) < 1e-9:
        return None
    return sample_std(clean) / abs(avg)


def count_negative(values: list[float | None]) -> int:
    return sum(1 for value in values if value is not None and value < 0)


def infer_roe(record: FinancialRecord) -> float | None:
    if record.roe is not None:
        return record.roe
    if record.net_income is None or record.shareholders_equity in (None, 0):
        return None
    return record.net_income / record.shareholders_equity


def latest_debt_to_equity(records: list[FinancialRecord]) -> float | None:
    latest_records = last_n_records(records, 1)
    if not latest_records:
        return None
    latest = latest_records[0]
    if latest.total_liabilities is None or latest.shareholders_equity in (None, 0):
        return None
    return latest.total_liabilities / latest.shareholders_equity


def free_cash_flow(record: FinancialRecord) -> float | None:
    if record.free_cash_flow is not None:
        return record.free_cash_flow
    if record.operating_cash_flow is None or record.capital_expenditure is None:
        return None
    return record.operating_cash_flow - abs(record.capital_expenditure)


def latest_asset_liability_ratio(records: list[FinancialRecord]) -> float | None:
    latest_records = last_n_records(records, 1)
    if not latest_records:
        return None
    latest = latest_records[0]
    if latest.asset_liability_ratio is not None:
        return latest.asset_liability_ratio
    if latest.total_liabilities is None or latest.total_assets in (None, 0):
        return None
    return latest.total_liabilities / latest.total_assets


def latest_goodwill_ratio(records: list[FinancialRecord]) -> float | None:
    latest_records = last_n_records(records, 1)
    if not latest_records:
        return None
    latest = latest_records[0]
    if latest.goodwill is None or latest.total_assets in (None, 0):
        return None
    return latest.goodwill / latest.total_assets


def latest_interest_coverage(records: list[FinancialRecord]) -> float | None:
    latest_records = last_n_records(records, 1)
    if not latest_records:
        return None
    latest = latest_records[0]
    if latest.ebit is None or latest.interest_expense in (None, 0):
        return None
    return latest.ebit / abs(latest.interest_expense)


def revenue_cagr(records: list[FinancialRecord], years: int = 5) -> float | None:
    period = sorted(last_n_records(records, years), key=lambda item: item.year)
    values = [record.revenue for record in period if record.revenue is not None]
    if len(values) < 2 or values[0] <= 0 or values[-1] <= 0:
        return None
    ratio = values[-1] / values[0]
    if ratio <= 0:
        return None
    return ratio ** (1 / (len(values) - 1)) - 1


def dividend_stability(records: list[FinancialRecord], years: int = 5) -> tuple[str, int]:
    period = sorted(last_n_records(records, years), key=lambda item: item.year)
    dividends = [
        record.dividends_paid
        for record in period
        if record.dividends_paid is not None and record.dividends_paid > 0
    ]
    if not dividends:
        return "未分红/不适用", 0
    paid_years = len(dividends)
    if paid_years < len(period):
        return "不连续", 1
    cut_count = sum(
        1
        for previous, current in zip(dividends, dividends[1:])
        if previous > 0 and current < previous * 0.75
    )
    if cut_count:
        return "有明显下滑", 1
    return "稳定", 0
