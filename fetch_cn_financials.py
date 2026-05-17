"""Fetch annual A-share financial data with AkShare."""

from __future__ import annotations

import argparse
import time
from typing import Any

from csv_utils import append_csv_rows, read_csv_rows
from financial_schema import RAW_FINANCIAL_HEADERS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="拉取A股年度财务数据")
    parser.add_argument("--input", default="data/universe/classified_universe.csv")
    parser.add_argument("--output", default="data/raw/cn_financials_raw.csv")
    parser.add_argument("--limit", type=int, help="最多处理多少只A股，用于20/500测试")
    parser.add_argument("--years", type=int, default=10)
    parser.add_argument("--sleep", type=float, default=0.4, help="每只股票之间的暂停秒数")
    parser.add_argument("--resume", action="store_true", help="跳过输出文件中已有的股票")
    return parser.parse_args()


def _number(value: Any) -> float | str:
    try:
        if value is None or value == "":
            return ""
        if hasattr(value, "item"):
            value = value.item()
        if value != value:
            return ""
        if isinstance(value, str):
            value = value.replace(",", "").replace("%", "").strip()
        return float(value)
    except (TypeError, ValueError):
        return ""


def _find_column(columns: list[str], aliases: tuple[str, ...]) -> str | None:
    for alias in aliases:
        for column in columns:
            if alias in column:
                return column
    return None


def _year(value: Any) -> int | None:
    text = str(value)
    for token in text.replace("/", "-").split("-"):
        if len(token) == 4 and token.isdigit():
            return int(token)
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return None


def _fetch_symbol(row: dict[str, str], years: int) -> list[dict[str, object]]:
    import akshare as ak

    symbol = row["symbol"].zfill(6)
    data = ak.stock_financial_abstract(symbol=symbol)
    if data is None or data.empty:
        raise RuntimeError("no financial abstract returned")

    aliases = {
        "revenue": ("营业总收入", "营业收入"),
        "net_income": ("归母净利润", "净利润"),
        "operating_cash_flow": ("经营活动产生的现金流量净额", "经营现金流"),
        "shareholders_equity": ("归属于母公司股东权益", "所有者权益", "股东权益"),
        "total_assets": ("资产总计", "总资产"),
        "total_liabilities": ("负债合计", "总负债"),
        "asset_liability_ratio": ("资产负债率",),
        "roe": ("净资产收益率", "ROE"),
    }
    metric_rows = {}
    for item in data.to_dict("records"):
        metric_name = str(item.get("指标", ""))
        for field, field_aliases in aliases.items():
            if field not in metric_rows and any(alias in metric_name for alias in field_aliases):
                metric_rows[field] = item

    annual_columns = [
        str(column)
        for column in data.columns
        if str(column).isdigit() and str(column).endswith("1231")
    ][:years]

    output_rows = []
    for column in annual_columns:
        year = _year(column)
        if year is None:
            continue
        output_rows.append(
            {
                "symbol": symbol,
                "market": "CN",
                "name": row.get("name", ""),
                "industry": row.get("industry", ""),
                "year": year,
                "revenue": _number(metric_rows.get("revenue", {}).get(column)),
                "net_income": _number(metric_rows.get("net_income", {}).get(column)),
                "operating_cash_flow": _number(
                    metric_rows.get("operating_cash_flow", {}).get(column)
                ),
                "shareholders_equity": _number(
                    metric_rows.get("shareholders_equity", {}).get(column)
                ),
                "total_assets": _number(metric_rows.get("total_assets", {}).get(column)),
                "total_liabilities": _number(
                    metric_rows.get("total_liabilities", {}).get(column)
                ),
                "asset_liability_ratio": _normalize_percent(
                    _number(metric_rows.get("asset_liability_ratio", {}).get(column))
                ),
                "goodwill": "",
                "roe": _normalize_percent(_number(metric_rows.get("roe", {}).get(column))),
                "source": "akshare.stock_financial_abstract",
                "status": "ok",
            }
        )

    if not output_rows:
        raise RuntimeError("financial abstract had no usable annual rows")
    return output_rows


def _normalize_percent(value: float | str) -> float | str:
    if value == "":
        return ""
    if abs(float(value)) > 1:
        return float(value) / 100
    return value


def main() -> None:
    args = parse_args()
    universe = [row for row in read_csv_rows(args.input) if row.get("market") == "CN"]
    if args.limit:
        universe = universe[: args.limit]

    done = set()
    if args.resume:
        done = {
            row["symbol"]
            for row in read_csv_rows(args.output)
            if row.get("status") in {"ok", "error"}
        }

    processed = 0
    for row in universe:
        symbol = row["symbol"].zfill(6)
        if symbol in done:
            continue
        try:
            rows = _fetch_symbol(row, args.years)
        except Exception as exc:
            rows = [
                {
                    "symbol": symbol,
                    "market": "CN",
                    "name": row.get("name", ""),
                    "industry": row.get("industry", ""),
                    "source": "akshare.stock_financial_abstract",
                    "status": "error",
                    "error": str(exc),
                }
            ]
        append_csv_rows(args.output, RAW_FINANCIAL_HEADERS, rows)
        processed += 1
        print(f"[CN] {processed}/{len(universe)} {symbol}: {rows[0].get('status')}")
        if args.sleep:
            time.sleep(args.sleep)


if __name__ == "__main__":
    main()
