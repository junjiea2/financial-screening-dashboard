"""Data loading adapters for manual CSV files and optional market sources."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from models import FinancialRecord, StockFinancials


def _to_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _to_int(value: str | None) -> int:
    if value is None or value == "":
        raise ValueError("year is required")
    return int(value)


def load_from_csv(path: str | Path) -> list[StockFinancials]:
    """Load one row per stock-year from a CSV file."""
    grouped: dict[tuple[str, str], dict[str, object]] = defaultdict(
        lambda: {"records": []}
    )

    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            symbol = row["symbol"].strip()
            market = row.get("market", "").strip() or "Unknown"
            key = (symbol, market)
            bucket = grouped[key]
            bucket["symbol"] = symbol
            bucket["market"] = market
            bucket["name"] = row.get("name") or None
            bucket["industry"] = row.get("industry") or None
            bucket["pe"] = _to_float(row.get("pe"))
            bucket["pb"] = _to_float(row.get("pb"))
            bucket["source"] = str(path)
            bucket["records"].append(
                FinancialRecord(
                    year=_to_int(row.get("year")),
                    revenue=_to_float(row.get("revenue")),
                    net_income=_to_float(row.get("net_income")),
                    operating_cash_flow=_to_float(row.get("operating_cash_flow")),
                    shareholders_equity=_to_float(row.get("shareholders_equity")),
                    total_assets=_to_float(row.get("total_assets")),
                    total_liabilities=_to_float(row.get("total_liabilities")),
                    asset_liability_ratio=_to_float(row.get("asset_liability_ratio")),
                    capital_expenditure=_to_float(row.get("capital_expenditure")),
                    free_cash_flow=_to_float(row.get("free_cash_flow")),
                    goodwill=_to_float(row.get("goodwill")),
                    ebit=_to_float(row.get("ebit")),
                    interest_expense=_to_float(row.get("interest_expense")),
                    dividends_paid=_to_float(row.get("dividends_paid")),
                    non_performing_loan_ratio=_to_float(
                        row.get("non_performing_loan_ratio")
                    ),
                    solvency_ratio=_to_float(row.get("solvency_ratio")),
                    duration_gap=_to_float(row.get("duration_gap")),
                    net_gearing_ratio=_to_float(row.get("net_gearing_ratio")),
                    roe=_to_float(row.get("roe")),
                )
            )

    return [
        StockFinancials(
            symbol=str(item["symbol"]),
            market=str(item["market"]),
            name=item.get("name") if isinstance(item.get("name"), str) else None,
            industry=(
                item.get("industry") if isinstance(item.get("industry"), str) else None
            ),
            pe=item.get("pe") if isinstance(item.get("pe"), float) else None,
            pb=item.get("pb") if isinstance(item.get("pb"), float) else None,
            records=item["records"],  # type: ignore[arg-type]
            source=str(item["source"]),
        )
        for item in grouped.values()
    ]


def load_sample_universe() -> list[StockFinancials]:
    """Small built-in universe for smoke tests and demos."""
    return [
        StockFinancials(
            symbol="AAPL",
            market="US",
            name="Apple",
            industry="Consumer Electronics",
            pe=28,
            pb=35,
            records=[
                FinancialRecord(
                    year=year,
                    revenue=260 + i * 12,
                    net_income=55 + i * 4,
                    operating_cash_flow=70 + i * 4,
                    shareholders_equity=80 + i,
                    total_assets=240 + i * 6,
                    total_liabilities=120 + i * 3,
                    capital_expenditure=10 + i * 0.5,
                    goodwill=2,
                    ebit=70 + i * 4,
                    interest_expense=2,
                    dividends_paid=13 + i * 0.5,
                    roe=0.55 + i * 0.02,
                )
                for i, year in enumerate(range(2016, 2026))
            ],
        ),
        StockFinancials(
            symbol="LOWPB",
            market="CN",
            name="低PB亏损样例",
            industry="Industrial",
            pe=7,
            pb=0.55,
            records=[
                FinancialRecord(
                    year=year,
                    revenue=100 - i * 2,
                    net_income=[6, 4, -2, 3, -5, 2, -1, 1, -3, 1][i],
                    operating_cash_flow=[8, -2, -3, 1, -4, -2, 2, -1, -2, 1][i],
                    shareholders_equity=120,
                    total_assets=200,
                    total_liabilities=80,
                    capital_expenditure=8,
                    goodwill=15,
                    ebit=[9, 7, -1, 5, -3, 4, 1, 3, -2, 2][i],
                    interest_expense=3,
                    dividends_paid=[2, 0, 0, 1, 0, 0, 0, 0, 0, 0][i],
                )
                for i, year in enumerate(range(2016, 2026))
            ],
        ),
        StockFinancials(
            symbol="BANKX",
            market="CN",
            name="银行样例",
            industry="Bank",
            pe=4,
            pb=0.5,
            records=[
                FinancialRecord(
                    year=year,
                    revenue=200 + i * 4,
                    net_income=30 + i,
                    operating_cash_flow=40 + i,
                    shareholders_equity=280 + i * 8,
                    total_assets=5000 + i * 200,
                    total_liabilities=4700 + i * 190,
                    capital_expenditure=5,
                    goodwill=0,
                    ebit=45 + i,
                    interest_expense=10,
                    dividends_paid=8 + i * 0.2,
                    non_performing_loan_ratio=0.012,
                    roe=0.10,
                )
                for i, year in enumerate(range(2016, 2026))
            ],
        ),
        StockFinancials(
            symbol="CYCL",
            market="US",
            name="周期股样例",
            industry="Materials",
            pe=6,
            pb=1.2,
            records=[
                FinancialRecord(
                    year=year,
                    revenue=[80, 130, 90, 180, 70, 200, 95, 160, 85, 190][i],
                    net_income=[4, 22, -3, 35, 2, 40, -2, 25, 1, 32][i],
                    operating_cash_flow=[8, 25, -1, 38, 4, 44, 0, 28, 3, 36][i],
                    shareholders_equity=100,
                    total_assets=220,
                    total_liabilities=100,
                    capital_expenditure=12,
                    goodwill=8,
                    ebit=[8, 28, 0, 40, 5, 46, 1, 30, 4, 36][i],
                    interest_expense=5,
                    dividends_paid=[0, 5, 0, 8, 0, 8, 0, 4, 0, 6][i],
                )
                for i, year in enumerate(range(2016, 2026))
            ],
        ),
    ]


def load_from_yfinance(symbols: list[str]) -> list[StockFinancials]:
    """Best-effort US stock loader.

    This adapter is intentionally optional because yfinance can change fields and
    does not reliably expose a full ten-year history for every metric.
    """
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError("Install yfinance first: pip install yfinance") from exc

    stocks: list[StockFinancials] = []
    for symbol in symbols:
        ticker = yf.Ticker(symbol)
        info = ticker.get_info()
        stock = StockFinancials(
            symbol=symbol,
            market="US",
            name=info.get("shortName"),
            industry=info.get("industry"),
            pe=info.get("trailingPE"),
            pb=info.get("priceToBook"),
            records=[],
            source="yfinance",
        )
        stocks.append(stock)
    return stocks
