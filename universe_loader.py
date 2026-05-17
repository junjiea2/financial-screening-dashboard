"""Build broad A-share and US stock universes for later screening."""

from __future__ import annotations

import csv
import io
import urllib.request
from pathlib import Path


NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"


def _read_pipe_file(url: str) -> list[dict[str, str]]:
    with urllib.request.urlopen(url, timeout=30) as response:
        text = response.read().decode("utf-8", errors="replace")
    lines = [line for line in text.splitlines() if line and not line.startswith("File ")]
    return list(csv.DictReader(io.StringIO("\n".join(lines)), delimiter="|"))


def fetch_us_universe() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in _read_pipe_file(NASDAQ_LISTED_URL):
        if row.get("Test Issue") == "Y":
            continue
        symbol = row.get("Symbol", "").strip()
        if symbol:
            rows.append(
                {
                    "symbol": symbol,
                    "market": "US",
                    "name": row.get("Security Name", ""),
                    "exchange": "NASDAQ",
                    "industry": "",
                    "source": "nasdaqtrader",
                }
            )

    for row in _read_pipe_file(OTHER_LISTED_URL):
        if row.get("Test Issue") == "Y":
            continue
        symbol = row.get("ACT Symbol", "").strip()
        if symbol:
            rows.append(
                {
                    "symbol": symbol,
                    "market": "US",
                    "name": row.get("Security Name", ""),
                    "exchange": row.get("Exchange", ""),
                    "industry": "",
                    "source": "nasdaqtrader",
                }
            )
    return rows


def fetch_a_share_universe() -> list[dict[str, str]]:
    try:
        import akshare as ak
    except ImportError as exc:
        raise RuntimeError("Install akshare first: pip install akshare") from exc

    data = ak.stock_info_a_code_name()
    rows: list[dict[str, str]] = []
    for item in data.to_dict("records"):
        code = str(item.get("code", "")).zfill(6)
        name = str(item.get("name", ""))
        if code:
            rows.append(
                {
                    "symbol": code,
                    "market": "CN",
                    "name": name,
                    "exchange": "A股",
                    "industry": "",
                    "source": "akshare",
                }
            )
    return rows


def write_universe_csv(rows: list[dict[str, str]], path: str | Path) -> None:
    headers = ["symbol", "market", "name", "exchange", "industry", "source"]
    with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def load_universe_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))

