"""Normalize raw US/CN financial rows into the screener CSV format."""

from __future__ import annotations

import argparse

from csv_utils import read_csv_rows, write_csv_rows
from financial_schema import NORMALIZED_FINANCIAL_HEADERS

NORMALIZE_SCORE_FIELDS = (
    "revenue",
    "net_income",
    "operating_cash_flow",
    "shareholders_equity",
    "total_assets",
    "total_liabilities",
    "capital_expenditure",
    "goodwill",
    "ebit",
    "interest_expense",
    "dividends_paid",
    "roe",
)
SOURCE_PRIORITY = {
    "fmp": 3,
    "sec": 2,
    "yfinance": 1,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="统一A股/美股财务字段")
    parser.add_argument("--us", default="data/raw/us_financials_raw.csv")
    parser.add_argument("--cn", default="data/raw/cn_financials_raw.csv")
    parser.add_argument("--cn-valuations", default="data/raw/cn_valuations_raw.csv")
    parser.add_argument("--output", default="data/normalized/full_financials.csv")
    return parser.parse_args()


def _float_text(value: str | None) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text == "":
        return ""
    try:
        return str(float(text.replace(",", "")))
    except ValueError:
        return ""


def _free_cash_flow(row: dict[str, str]) -> str:
    operating_cash_flow = _float_text(row.get("operating_cash_flow"))
    capex = _float_text(row.get("capital_expenditure"))
    if operating_cash_flow == "" or capex == "":
        return ""
    return str(float(operating_cash_flow) - abs(float(capex)))


def _normalize_row(row: dict[str, str]) -> dict[str, str]:
    normalized = {
        "symbol": row.get("symbol", "").strip(),
        "market": row.get("market", "").strip(),
        "name": row.get("name", "").strip(),
        "industry": row.get("industry", "").strip(),
        "pe": _float_text(row.get("pe")),
        "pb": _float_text(row.get("pb")),
        "year": row.get("year", "").strip(),
        "revenue": _float_text(row.get("revenue")),
        "net_income": _float_text(row.get("net_income")),
        "operating_cash_flow": _float_text(row.get("operating_cash_flow")),
        "shareholders_equity": _float_text(row.get("shareholders_equity")),
        "total_assets": _float_text(row.get("total_assets")),
        "total_liabilities": _float_text(row.get("total_liabilities")),
        "asset_liability_ratio": _float_text(row.get("asset_liability_ratio")),
        "capital_expenditure": _float_text(row.get("capital_expenditure")),
        "free_cash_flow": _free_cash_flow(row),
        "goodwill": _float_text(row.get("goodwill")),
        "ebit": _float_text(row.get("ebit")),
        "interest_expense": _float_text(row.get("interest_expense")),
        "dividends_paid": _float_text(row.get("dividends_paid")),
        "non_performing_loan_ratio": _float_text(row.get("non_performing_loan_ratio")),
        "solvency_ratio": _float_text(row.get("solvency_ratio")),
        "duration_gap": _float_text(row.get("duration_gap")),
        "net_gearing_ratio": _float_text(row.get("net_gearing_ratio")),
        "roe": _float_text(row.get("roe")),
    }
    return normalized


def _normalized_score(normalized: dict[str, str], source: str | None = None) -> tuple[int, int]:
    filled_fields = sum(1 for field in NORMALIZE_SCORE_FIELDS if normalized.get(field))
    return filled_fields, SOURCE_PRIORITY.get((source or "").lower(), 0)


def _valuation_map(path: str) -> dict[str, dict[str, str]]:
    valuations = {}
    for row in read_csv_rows(path):
        if row.get("status") != "ok":
            continue
        symbol = row.get("symbol", "").strip().zfill(6)
        pe = _float_text(row.get("pe"))
        pb = _float_text(row.get("pb"))
        if symbol and (pe or pb):
            valuations[symbol] = {"pe": pe, "pb": pb}
    return valuations


def normalize_financial_rows(
    us_rows: list[dict[str, str]],
    cn_rows: list[dict[str, str]],
    cn_valuations: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    normalized_by_key: dict[tuple[str, str, str], dict[str, str]] = {}
    score_by_key: dict[tuple[str, str, str], tuple[int, int]] = {}
    valuations = cn_valuations or {}
    for row in us_rows + cn_rows:
        if row.get("status") != "ok" or not row.get("year"):
            continue
        normalized = _normalize_row(row)
        if normalized["market"] == "CN":
            valuation = valuations.get(normalized["symbol"].zfill(6), {})
            normalized["pe"] = normalized["pe"] or valuation.get("pe", "")
            normalized["pb"] = normalized["pb"] or valuation.get("pb", "")
        key = (normalized["symbol"], normalized["market"], normalized["year"])
        score = _normalized_score(normalized, row.get("source"))
        if key in normalized_by_key and score <= score_by_key[key]:
            continue
        normalized_by_key[key] = normalized
        score_by_key[key] = score

    normalized_rows = list(normalized_by_key.values())
    normalized_rows.sort(key=lambda item: (item["market"], item["symbol"], item["year"]))
    return normalized_rows


def main() -> None:
    args = parse_args()
    cn_valuations = _valuation_map(args.cn_valuations)
    normalized_rows = normalize_financial_rows(
        read_csv_rows(args.us),
        read_csv_rows(args.cn),
        cn_valuations,
    )
    write_csv_rows(args.output, NORMALIZED_FINANCIAL_HEADERS, normalized_rows)
    print(f"Wrote {len(normalized_rows)} normalized annual rows to {args.output}")


if __name__ == "__main__":
    main()
