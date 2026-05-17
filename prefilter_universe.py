"""Prefilter a broad stock universe into an investable candidate universe."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


OUTPUT_HEADERS = [
    "symbol",
    "market",
    "name",
    "exchange",
    "industry",
    "industry_profile",
    "core_metrics",
    "source",
    "prefilter_status",
    "prefilter_reason",
]


US_BLOCKED_NAME_TERMS = (
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
    "acquisition corp",
    "acquisition inc",
    "acquisition company",
    "acquisition co",
    "blank check",
    "shell companies",
)

US_BLOCKED_SYMBOL_SUFFIXES = (
    "W",
    "WS",
    "WT",
    "U",
    "R",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="预筛股票池，生成可投资候选 universe")
    parser.add_argument("--input", default="data/universe/classified_universe.csv")
    parser.add_argument("--output", default="data/universe/investable_universe.csv")
    parser.add_argument("--rejected-output", default="data/universe/rejected_universe.csv")
    parser.add_argument(
        "--include-adr",
        action="store_true",
        help="默认过滤ADR；加此参数保留ADR",
    )
    parser.add_argument(
        "--include-beijing",
        action="store_true",
        help="默认过滤北交所/8开头A股；加此参数保留",
    )
    return parser.parse_args()


def read_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: str | Path, rows: list[dict[str, str]]) -> None:
    with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_HEADERS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def is_us_common_stock(row: dict[str, str], include_adr: bool) -> tuple[bool, str]:
    symbol = (row.get("symbol") or "").upper()
    name = (row.get("name") or "").lower()
    if any(term in name for term in US_BLOCKED_NAME_TERMS):
        return False, "US非普通经营公司证券/基金/权证/Units/Rights/SPAC"
    if not include_adr and (
        "american depositary" in name
        or "american depository" in name
        or " adr" in name
    ):
        return False, "US ADR暂不纳入第一批可投资池"
    if symbol.endswith(US_BLOCKED_SYMBOL_SUFFIXES) and (
        "warrant" in name or "right" in name or "unit" in name
    ):
        return False, "US衍生证券后缀"
    if "." in symbol or "/" in symbol:
        return False, "US特殊 share class 暂不纳入第一批"
    return True, "通过基础普通股预筛"


def is_cn_investable(row: dict[str, str], include_beijing: bool) -> tuple[bool, str]:
    symbol = row.get("symbol") or ""
    name = row.get("name") or ""
    if "ST" in name.upper() or "*ST" in name.upper():
        return False, "A股ST/*ST"
    if not include_beijing and (symbol.startswith("8") or symbol.startswith("4")):
        return False, "北交所/新三板类标的暂不纳入第一批"
    return True, "通过A股基础预筛"


def annotate(row: dict[str, str], status: str, reason: str) -> dict[str, str]:
    output = {header: row.get(header, "") for header in OUTPUT_HEADERS}
    output["prefilter_status"] = status
    output["prefilter_reason"] = reason
    return output


def main() -> None:
    args = parse_args()
    rows = read_rows(args.input)
    accepted: list[dict[str, str]] = []
    rejected: list[dict[str, str]] = []

    for row in rows:
        market = row.get("market")
        if market == "US":
            ok, reason = is_us_common_stock(row, args.include_adr)
        elif market == "CN":
            ok, reason = is_cn_investable(row, args.include_beijing)
        else:
            ok, reason = False, "未知市场"

        if ok:
            accepted.append(annotate(row, "accepted", reason))
        else:
            rejected.append(annotate(row, "rejected", reason))

    write_rows(args.output, accepted)
    write_rows(args.rejected_output, rejected)
    print(f"Accepted: {len(accepted)} -> {args.output}")
    print(f"Rejected: {len(rejected)} -> {args.rejected_output}")


if __name__ == "__main__":
    main()
