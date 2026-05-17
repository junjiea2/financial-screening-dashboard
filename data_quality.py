"""Data quality scoring for financial screening."""

from __future__ import annotations

from models import FinancialRecord


IMPORTANT_FIELDS = (
    "revenue",
    "net_income",
    "operating_cash_flow",
    "shareholders_equity",
    "total_assets",
    "total_liabilities",
)


def _has_roe_or_equity(record: FinancialRecord) -> bool:
    return record.roe is not None or record.shareholders_equity is not None


def _has_balance_sheet_anchor(record: FinancialRecord) -> bool:
    return record.asset_liability_ratio is not None or (
        record.total_assets is not None and record.total_liabilities is not None
    )


def complete_year_count(records: list[FinancialRecord]) -> int:
    complete = 0
    for record in records:
        if (
            record.revenue is not None
            and record.net_income is not None
            and _has_roe_or_equity(record)
            and _has_balance_sheet_anchor(record)
        ):
            complete += 1
    return complete


def missing_field_count(records: list[FinancialRecord]) -> int:
    missing = 0
    for record in records:
        for field in IMPORTANT_FIELDS:
            if getattr(record, field) is None:
                missing += 1
    return missing


def score_data_quality(
    records: list[FinancialRecord],
    market: str | None = None,
) -> tuple[int, int, int, str]:
    data_years = complete_year_count(records)
    missing_count = missing_field_count(records)
    market_code = (market or "").upper()
    if market_code == "US":
        if data_years >= 6:
            level = "High"
        elif data_years >= 3:
            level = "Medium"
        elif data_years > 0:
            level = "Low"
        else:
            level = "Insufficient"
        score = min(100, int(data_years / 5 * 100))
    else:
        if data_years >= 8:
            level = "High"
        elif data_years >= 5:
            level = "Medium"
        elif data_years > 0:
            level = "Low"
        else:
            level = "Insufficient"
        score = min(100, int(data_years / 8 * 100))

    if level == "Insufficient":
        score = 0
    return data_years, missing_count, score, level
