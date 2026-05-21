"""Fetch annual US financial statements with FMP or yfinance fallback."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any
import urllib.parse
import urllib.request

from csv_utils import append_csv_rows, read_csv_rows
from fmp_client import FMPClient
from financial_schema import RAW_FINANCIAL_HEADERS


SEC_TICKER_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SEC_USER_AGENT = "financial-screening-dashboard/1.0 research@example.com"
SEC_CONCEPTS = {
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ),
    "net_income": ("NetIncomeLoss",),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
    "shareholders_equity": (
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ),
    "total_assets": ("Assets",),
    "total_liabilities": ("Liabilities",),
    "capital_expenditure": (
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ),
    "goodwill": ("Goodwill",),
    "ebit": ("OperatingIncomeLoss",),
    "interest_expense": ("InterestExpenseNonOperating", "InterestExpense"),
    "dividends_paid": (
        "PaymentsOfDividendsCommonStock",
        "PaymentsOfDividends",
        "PaymentsOfDividendsAndDividendEquivalentsOnCommonStockAndRestrictedStockUnits",
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="拉取美股年度财务数据")
    parser.add_argument("--input", default="data/universe/classified_universe.csv")
    parser.add_argument("--output", default="data/raw/us_financials_raw.csv")
    parser.add_argument("--limit", type=int, help="最多处理多少只美股，用于20/500测试")
    parser.add_argument("--years", type=int, default=10)
    parser.add_argument("--sleep", type=float, default=0.2, help="每只股票之间的暂停秒数")
    parser.add_argument("--resume", action="store_true", help="跳过输出文件中已有的股票")
    parser.add_argument(
        "--resume-min-ok-years",
        type=int,
        default=1,
        help="resume时，只有已有ok年份数达到该值才跳过；补历史可设为8或10",
    )
    parser.add_argument(
        "--provider",
        choices=["auto", "fmp", "sec", "yfinance"],
        default="auto",
        help="美股数据源：auto优先FMP，其次SEC，最后fallback到yfinance",
    )
    parser.add_argument("--fmp-api-key", help="FMP API key；也可用环境变量 FMP_API_KEY")
    parser.add_argument("--sec-user-agent", help="SEC User-Agent；也可用环境变量 SEC_USER_AGENT")
    parser.add_argument("--cache-dir", default="cache/us_financials")
    parser.add_argument("--no-cache", action="store_true")
    return parser.parse_args()


def _number(value: Any) -> float | str:
    try:
        if value is None:
            return ""
        if hasattr(value, "item"):
            value = value.item()
        if value != value:
            return ""
        return float(value)
    except (TypeError, ValueError):
        return ""


def _statement_value(statement: Any, aliases: tuple[str, ...], column: Any) -> float | str:
    if statement is None or getattr(statement, "empty", True):
        return ""
    if column not in statement.columns:
        return ""
    for alias in aliases:
        if alias in statement.index:
            return _number(statement.loc[alias, column])
    return ""


def _year_from_column(column: Any) -> int | None:
    try:
        return int(column.year)
    except AttributeError:
        try:
            return datetime.fromisoformat(str(column)).year
        except ValueError:
            return None


def _request_json(
    url: str,
    cache_path: Path,
    user_agent: str,
    use_cache: bool = True,
    sleep_seconds: float = 0.2,
) -> Any:
    if use_cache and cache_path.exists():
        with cache_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    if sleep_seconds:
        time.sleep(sleep_seconds)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Host": urllib.parse.urlparse(url).netloc,
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read()
    text = data.decode("utf-8")
    payload = json.loads(text)
    if use_cache:
        with cache_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)
    return payload


def _sec_ticker_map(
    cache_dir: str | Path,
    user_agent: str,
    use_cache: bool = True,
    sleep_seconds: float = 0.2,
) -> dict[str, int]:
    payload = _request_json(
        SEC_TICKER_URL,
        Path(cache_dir) / "sec" / "company_tickers.json",
        user_agent,
        use_cache=use_cache,
        sleep_seconds=sleep_seconds,
    )
    return {
        str(item.get("ticker", "")).upper(): int(item["cik_str"])
        for item in payload.values()
        if item.get("ticker") and item.get("cik_str")
    }


def _sec_fact_year(fact: dict[str, Any]) -> int | None:
    frame = str(fact.get("frame") or "")
    frame_match = re.fullmatch(r"CY(\d{4})", frame)
    if frame_match:
        return int(frame_match.group(1))
    end = str(fact.get("end", ""))
    if len(end) >= 4:
        try:
            return int(end[:4])
        except ValueError:
            pass
    try:
        return int(fact.get("fy"))
    except (TypeError, ValueError):
        return None


def _is_annual_sec_fact(fact: dict[str, Any]) -> bool:
    frame = str(fact.get("frame") or "")
    if "Q" in frame:
        return False
    start = fact.get("start")
    end = fact.get("end")
    if start and end:
        try:
            start_date = datetime.fromisoformat(str(start))
            end_date = datetime.fromisoformat(str(end))
        except ValueError:
            return True
        return (end_date - start_date).days >= 300
    return True


def _sec_values_by_year(
    facts: dict[str, Any],
    concepts: tuple[str, ...],
    allowed_units: tuple[str, ...] = ("USD",),
) -> dict[int, float]:
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    values: dict[int, float] = {}
    for concept in concepts:
        concept_values: dict[int, tuple[str, float]] = {}
        units = us_gaap.get(concept, {}).get("units", {})
        for unit, records in units.items():
            if unit not in allowed_units:
                continue
            for fact in records:
                if fact.get("form") not in {"10-K", "10-K/A"}:
                    continue
                if fact.get("fp") not in {"FY", None, ""}:
                    continue
                if not _is_annual_sec_fact(fact):
                    continue
                year = _sec_fact_year(fact)
                if year is None or fact.get("val") in {None, ""}:
                    continue
                filed = str(fact.get("filed", ""))
                parsed_value = _number(fact.get("val"))
                if parsed_value == "":
                    continue
                if year not in concept_values or filed > concept_values[year][0]:
                    concept_values[year] = (filed, float(parsed_value))
        for year, (_, value) in concept_values.items():
            values.setdefault(year, value)
    return values


def _rows_from_sec_companyfacts(
    row: dict[str, str],
    facts: dict[str, Any],
    years: int,
) -> list[dict[str, object]]:
    values_by_field = {
        field: _sec_values_by_year(facts, concepts)
        for field, concepts in SEC_CONCEPTS.items()
    }
    all_years = sorted(
        {year for values in values_by_field.values() for year in values},
        reverse=True,
    )[:years]
    if not all_years:
        raise RuntimeError("SEC returned no usable annual rows")

    entity_name = facts.get("entityName", "")
    output_rows: list[dict[str, object]] = []
    for year in all_years:
        output_rows.append(
            {
                "symbol": row["symbol"],
                "market": "US",
                "name": row.get("name") or entity_name,
                "industry": row.get("industry", ""),
                "year": year,
                "pe": "",
                "pb": "",
                "revenue": values_by_field["revenue"].get(year, ""),
                "net_income": values_by_field["net_income"].get(year, ""),
                "operating_cash_flow": values_by_field["operating_cash_flow"].get(year, ""),
                "shareholders_equity": values_by_field["shareholders_equity"].get(year, ""),
                "total_assets": values_by_field["total_assets"].get(year, ""),
                "total_liabilities": values_by_field["total_liabilities"].get(year, ""),
                "capital_expenditure": values_by_field["capital_expenditure"].get(year, ""),
                "goodwill": values_by_field["goodwill"].get(year, ""),
                "ebit": values_by_field["ebit"].get(year, ""),
                "interest_expense": values_by_field["interest_expense"].get(year, ""),
                "dividends_paid": values_by_field["dividends_paid"].get(year, ""),
                "source": "sec",
                "status": "ok",
            }
        )
    return output_rows


def _fetch_symbol_sec(
    row: dict[str, str],
    years: int,
    ticker_map: dict[str, int],
    cache_dir: str | Path,
    user_agent: str,
    use_cache: bool = True,
    sleep_seconds: float = 0.2,
) -> list[dict[str, object]]:
    symbol = row["symbol"].upper()
    cik = ticker_map.get(symbol)
    if cik is None:
        raise RuntimeError("SEC CIK not found")
    facts = _request_json(
        SEC_FACTS_URL.format(cik=f"{cik:010d}"),
        Path(cache_dir) / "sec" / "companyfacts" / f"{symbol}.json",
        user_agent,
        use_cache=use_cache,
        sleep_seconds=sleep_seconds,
    )
    return _rows_from_sec_companyfacts(row, facts, years)


def _fetch_symbol(row: dict[str, str], years: int) -> list[dict[str, object]]:
    import yfinance as yf

    symbol = row["symbol"]
    ticker = yf.Ticker(symbol)
    info = ticker.get_info()
    income = ticker.income_stmt
    balance = ticker.balance_sheet
    cashflow = ticker.cashflow

    if income.empty and balance.empty and cashflow.empty:
        raise RuntimeError("no annual statements returned")

    columns = []
    for statement in (income, balance, cashflow):
        if not statement.empty:
            columns.extend(statement.columns)
    unique_columns = sorted(set(columns), reverse=True)[:years]

    output_rows = []
    for column in unique_columns:
        year = _year_from_column(column)
        if year is None:
            continue
        output_rows.append(
            {
                "symbol": symbol,
                "market": "US",
                "name": row.get("name") or info.get("shortName", ""),
                "industry": row.get("industry") or info.get("industry", ""),
                "year": year,
                "pe": _number(info.get("trailingPE")),
                "pb": _number(info.get("priceToBook")),
                "revenue": _statement_value(
                    income, ("Total Revenue", "Operating Revenue"), column
                ),
                "net_income": _statement_value(
                    income,
                    ("Net Income", "Net Income Common Stockholders"),
                    column,
                ),
                "operating_cash_flow": _statement_value(
                    cashflow, ("Operating Cash Flow", "Total Cash From Operating Activities"), column
                ),
                "shareholders_equity": _statement_value(
                    balance,
                    ("Stockholders Equity", "Total Equity Gross Minority Interest"),
                    column,
                ),
                "total_assets": _statement_value(balance, ("Total Assets",), column),
                "total_liabilities": _statement_value(
                    balance,
                    ("Total Liabilities Net Minority Interest", "Total Liab"),
                    column,
                ),
                "capital_expenditure": _statement_value(
                    cashflow, ("Capital Expenditure", "Capital Expenditures"), column
                ),
                "goodwill": _statement_value(balance, ("Goodwill",), column),
                "ebit": _statement_value(income, ("EBIT", "Operating Income"), column),
                "interest_expense": _statement_value(
                    income, ("Interest Expense", "Interest Expense Non Operating"), column
                ),
                "dividends_paid": _statement_value(
                    cashflow,
                    ("Cash Dividends Paid", "Common Stock Dividend Paid"),
                    column,
                ),
                "source": "yfinance",
                "status": "ok",
            }
        )
    if not output_rows:
        raise RuntimeError("statements had no usable annual columns")
    return output_rows


def _value(record: dict[str, Any] | None, *keys: str) -> float | str:
    if not record:
        return ""
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return _number(record[key])
    return ""


def _by_year(records: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    output = {}
    for record in records or []:
        year = None
        if record.get("calendarYear"):
            try:
                year = int(record["calendarYear"])
            except (TypeError, ValueError):
                year = None
        if year is None and record.get("date"):
            try:
                year = int(str(record["date"])[:4])
            except ValueError:
                year = None
        if year is not None:
            output[year] = record
    return output


def _fetch_symbol_fmp(
    row: dict[str, str],
    years: int,
    client: FMPClient,
) -> list[dict[str, object]]:
    symbol = row["symbol"]
    payload = client.fetch_fundamentals(symbol, years)
    income_by_year = _by_year(payload.get("income_statement", []))
    balance_by_year = _by_year(payload.get("balance_sheet", []))
    cash_by_year = _by_year(payload.get("cash_flow", []))
    metrics_by_year = _by_year(payload.get("key_metrics", []))
    profile = (payload.get("profile") or [{}])[0] if isinstance(payload.get("profile"), list) else {}

    all_years = sorted(
        set(income_by_year) | set(balance_by_year) | set(cash_by_year) | set(metrics_by_year),
        reverse=True,
    )[:years]
    if not all_years:
        raise RuntimeError("FMP returned no usable annual rows")

    output_rows = []
    for year in all_years:
        income = income_by_year.get(year, {})
        balance = balance_by_year.get(year, {})
        cash = cash_by_year.get(year, {})
        metrics = metrics_by_year.get(year, {})
        output_rows.append(
            {
                "symbol": symbol,
                "market": "US",
                "name": row.get("name") or profile.get("companyName", ""),
                "industry": row.get("industry") or profile.get("industry", ""),
                "year": year,
                "pe": _value(metrics, "peRatio", "peRatioTTM"),
                "pb": _value(metrics, "pbRatio", "priceToBookRatio"),
                "revenue": _value(income, "revenue"),
                "net_income": _value(income, "netIncome"),
                "operating_cash_flow": _value(cash, "operatingCashFlow"),
                "shareholders_equity": _value(
                    balance,
                    "totalEquity",
                    "totalStockholdersEquity",
                    "totalStockholdersEquityAndNoncontrollingInterest",
                ),
                "total_assets": _value(balance, "totalAssets"),
                "total_liabilities": _value(balance, "totalLiabilities"),
                "capital_expenditure": _value(cash, "capitalExpenditure"),
                "goodwill": _value(balance, "goodwill"),
                "ebit": _value(income, "ebit", "operatingIncome"),
                "interest_expense": _value(income, "interestExpense"),
                "dividends_paid": _value(cash, "dividendsPaid"),
                "roe": _value(metrics, "roe"),
                "source": "fmp",
                "status": "ok",
            }
        )
    return output_rows


def _is_probably_operating_equity(row: dict[str, str]) -> bool:
    name = (row.get("name") or "").lower()
    blocked_terms = (
        "etf",
        "closed end fund",
        "exchange traded",
        "warrant",
        "warrants",
        " - right",
        "rights",
        " - unit",
        " - units",
        "note due",
        "senior notes",
        "preferred",
        "depositary shares",
    )
    return not any(term in name for term in blocked_terms)


def main() -> None:
    args = parse_args()
    universe = [row for row in read_csv_rows(args.input) if row.get("market") == "US"]
    if args.limit:
        universe = universe[: args.limit]

    done = set()
    if args.resume:
        ok_years_by_symbol: dict[str, set[str]] = {}
        skipped_symbols = set()
        error_symbols = set()
        for row in read_csv_rows(args.output):
            symbol = row.get("symbol", "")
            if not symbol:
                continue
            if row.get("status") == "ok" and row.get("year"):
                ok_years_by_symbol.setdefault(symbol, set()).add(row["year"])
            elif row.get("status") == "skipped":
                skipped_symbols.add(symbol)
            elif row.get("status") == "error":
                error_symbols.add(symbol)
        done = {
            symbol
            for symbol, years in ok_years_by_symbol.items()
            if len(years) >= args.resume_min_ok_years
        }
        done |= skipped_symbols
        if args.resume_min_ok_years <= 1:
            done |= error_symbols

    fmp_client: FMPClient | None = None
    if args.provider in {"auto", "fmp"}:
        try:
            fmp_client = FMPClient(
                api_key=args.fmp_api_key,
                cache_dir=args.cache_dir,
                sleep_seconds=args.sleep,
                use_cache=not args.no_cache,
            )
        except Exception as exc:
            if args.provider == "fmp":
                raise
            print(f"[US] FMP unavailable, falling back to yfinance: {exc}")

    sec_tickers: dict[str, int] | None = None
    sec_user_agent = args.sec_user_agent or os.environ.get("SEC_USER_AGENT", SEC_USER_AGENT)
    if args.provider in {"auto", "sec"}:
        try:
            sec_tickers = _sec_ticker_map(
                args.cache_dir,
                sec_user_agent,
                use_cache=not args.no_cache,
                sleep_seconds=args.sleep,
            )
        except Exception as exc:
            if args.provider == "sec":
                raise
            print(f"[US] SEC ticker map unavailable, falling back to yfinance: {exc}")

    processed = 0
    for row in universe:
        symbol = row["symbol"]
        if symbol in done:
            continue
        if not _is_probably_operating_equity(row):
            rows = [
                {
                    "symbol": symbol,
                    "market": "US",
                    "name": row.get("name", ""),
                    "industry": row.get("industry", ""),
                    "source": "yfinance",
                    "status": "skipped",
                    "error": "non-operating security type",
                }
            ]
        else:
            try:
                if args.provider in {"auto", "fmp"} and fmp_client is not None:
                    try:
                        rows = _fetch_symbol_fmp(row, args.years, fmp_client)
                    except Exception:
                        if args.provider == "fmp":
                            raise
                        if sec_tickers is not None:
                            try:
                                rows = _fetch_symbol_sec(
                                    row,
                                    args.years,
                                    sec_tickers,
                                    args.cache_dir,
                                    sec_user_agent,
                                    use_cache=not args.no_cache,
                                    sleep_seconds=args.sleep,
                                )
                            except Exception:
                                rows = _fetch_symbol(row, args.years)
                        else:
                            rows = _fetch_symbol(row, args.years)
                elif args.provider in {"auto", "sec"} and sec_tickers is not None:
                    try:
                        rows = _fetch_symbol_sec(
                            row,
                            args.years,
                            sec_tickers,
                            args.cache_dir,
                            sec_user_agent,
                            use_cache=not args.no_cache,
                            sleep_seconds=args.sleep,
                        )
                    except Exception:
                        if args.provider == "sec":
                            raise
                        rows = _fetch_symbol(row, args.years)
                else:
                    rows = _fetch_symbol(row, args.years)
            except Exception as exc:
                rows = [
                    {
                        "symbol": symbol,
                        "market": "US",
                        "name": row.get("name", ""),
                        "industry": row.get("industry", ""),
                        "source": args.provider,
                        "status": "error",
                        "error": str(exc),
                    }
                ]
        append_csv_rows(args.output, RAW_FINANCIAL_HEADERS, rows)
        processed += 1
        print(f"[US] {processed}/{len(universe)} {symbol}: {rows[0].get('status')}")
        if args.sleep and (args.provider == "yfinance" or fmp_client is None):
            time.sleep(args.sleep)


if __name__ == "__main__":
    main()
