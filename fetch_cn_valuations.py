"""Fetch current A-share PE/PB valuation data with AkShare."""

from __future__ import annotations

import argparse
import time
from typing import Any

from csv_utils import append_csv_rows, read_csv_rows, write_csv_rows


VALUATION_HEADERS = [
    "symbol",
    "market",
    "name",
    "pe",
    "pb",
    "source",
    "status",
    "error",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="拉取A股PE/PB估值数据")
    parser.add_argument("--input", default="data/universe/investable_universe.csv")
    parser.add_argument("--output", default="data/raw/cn_valuations_raw.csv")
    parser.add_argument("--limit", type=int, help="最多输出多少只A股，用于小样本测试")
    parser.add_argument("--provider", choices=["stock-value-em", "spot-em"], default="stock-value-em")
    parser.add_argument("--sleep", type=float, default=0.2, help="逐只股票模式下每只股票之间的暂停秒数")
    parser.add_argument("--resume", action="store_true", help="跳过输出文件中已有的股票")
    return parser.parse_args()


def _number(value: Any) -> str:
    try:
        if value is None or value == "":
            return ""
        if hasattr(value, "item"):
            value = value.item()
        if value != value:
            return ""
        if isinstance(value, str):
            value = value.replace(",", "").replace("%", "").strip()
        number = float(value)
        if number == 0:
            return ""
        return str(number)
    except (TypeError, ValueError):
        return ""


def _first_value(row: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    normalized = {str(key).replace(" ", "").lower(): value for key, value in row.items()}
    for alias in aliases:
        key = alias.replace(" ", "").lower()
        if key in normalized:
            return normalized[key]
    for key, value in row.items():
        text = str(key).replace(" ", "").lower()
        if any(alias.replace(" ", "").lower() in text for alias in aliases):
            return value
    return ""


def fetch_spot_valuations() -> list[dict[str, str]]:
    import akshare as ak

    data = ak.stock_zh_a_spot_em()
    if data is None or data.empty:
        raise RuntimeError("no A-share spot valuation data returned")

    rows: list[dict[str, str]] = []
    for item in data.to_dict("records"):
        symbol = str(_first_value(item, ("代码", "symbol"))).strip().zfill(6)
        if not symbol or symbol == "000000":
            continue
        rows.append(
            {
                "symbol": symbol,
                "market": "CN",
                "name": str(_first_value(item, ("名称", "name"))).strip(),
                "pe": _number(_first_value(item, ("市盈率-动态", "市盈率", "PE", "pe"))),
                "pb": _number(_first_value(item, ("市净率", "PB", "pb"))),
                "source": "akshare.stock_zh_a_spot_em",
                "status": "ok",
                "error": "",
            }
        )
    return rows


def fetch_symbol_valuation(row: dict[str, str]) -> dict[str, str]:
    import akshare as ak

    symbol = row["symbol"].zfill(6)
    data = ak.stock_value_em(symbol=symbol)
    if data is None or data.empty:
        raise RuntimeError("no valuation data returned")
    latest = data.to_dict("records")[-1]
    return {
        "symbol": symbol,
        "market": "CN",
        "name": row.get("name", ""),
        "pe": _number(_first_value(latest, ("PE(TTM)", "PE(静)", "市盈率"))),
        "pb": _number(_first_value(latest, ("市净率", "PB", "pb"))),
        "source": "akshare.stock_value_em",
        "status": "ok",
        "error": "",
    }


def main() -> None:
    args = parse_args()
    universe = [
        {**row, "symbol": row["symbol"].zfill(6)}
        for row in read_csv_rows(args.input)
        if row.get("market") == "CN" and row.get("symbol")
    ]
    if args.limit:
        universe = universe[: args.limit]

    if args.provider == "spot-em":
        wanted = {row["symbol"] for row in universe}
        rows = [row for row in fetch_spot_valuations() if not wanted or row["symbol"] in wanted]
        write_csv_rows(args.output, VALUATION_HEADERS, rows)
        print(f"Wrote {len(rows)} CN valuation rows to {args.output}")
        return

    done = set()
    if args.resume:
        done = {
            row["symbol"].zfill(6)
            for row in read_csv_rows(args.output)
            if row.get("status") in {"ok", "error"} and row.get("symbol")
        }

    processed = 0
    for row in universe:
        symbol = row["symbol"]
        if symbol in done:
            continue
        try:
            output_row = fetch_symbol_valuation(row)
        except Exception as exc:
            output_row = {
                "symbol": symbol,
                "market": "CN",
                "name": row.get("name", ""),
                "pe": "",
                "pb": "",
                "source": "akshare.stock_value_em",
                "status": "error",
                "error": str(exc),
            }
        append_csv_rows(args.output, VALUATION_HEADERS, [output_row])
        processed += 1
        print(f"[CN估值] {processed}/{len(universe)} {symbol}: {output_row['status']}")
        if args.sleep:
            time.sleep(args.sleep)


if __name__ == "__main__":
    main()
