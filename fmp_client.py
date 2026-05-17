"""Financial Modeling Prep client with rate limiting and local cache."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


class FMPClient:
    """Small synchronous FMP client for annual fundamentals."""

    def __init__(
        self,
        api_key: str | None = None,
        cache_dir: str | Path = "cache/us_financials",
        sleep_seconds: float = 0.2,
        retries: int = 3,
        use_cache: bool = True,
    ) -> None:
        self.api_key = api_key or os.environ.get("FMP_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("FMP_API_KEY is required for FMP mode")
        self.cache_dir = Path(cache_dir)
        self.sleep_seconds = sleep_seconds
        self.retries = retries
        self.use_cache = use_cache
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch_fundamentals(self, symbol: str, limit: int = 10) -> dict[str, Any]:
        cache_path = self.cache_dir / f"{_safe_symbol(symbol)}.json"
        if self.use_cache and cache_path.exists():
            with cache_path.open("r", encoding="utf-8") as handle:
                return json.load(handle)

        payload = {
            "income_statement": self._get_v3(
                f"income-statement/{symbol}", {"period": "annual", "limit": limit}
            ),
            "balance_sheet": self._get_v3(
                f"balance-sheet-statement/{symbol}",
                {"period": "annual", "limit": limit},
            ),
            "cash_flow": self._get_v3(
                f"cash-flow-statement/{symbol}", {"period": "annual", "limit": limit}
            ),
            "key_metrics": self._get_v3(
                f"key-metrics/{symbol}", {"period": "annual", "limit": limit}
            ),
            "profile": self._get_v3(f"profile/{symbol}", {}),
        }

        if self.use_cache:
            with cache_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
        return payload

    def _get_v3(self, path: str, params: dict[str, Any]) -> Any:
        query = dict(params)
        query["apikey"] = self.api_key
        url = f"https://financialmodelingprep.com/api/v3/{path}?{urllib.parse.urlencode(query)}"
        return self._request_json(url)

    def _request_json(self, url: str) -> Any:
        last_error: Exception | None = None
        for attempt in range(self.retries):
            if self.sleep_seconds:
                time.sleep(self.sleep_seconds)
            try:
                request = urllib.request.Request(
                    url,
                    headers={"User-Agent": "financial-minefield-screener/1.0"},
                )
                with urllib.request.urlopen(request, timeout=30) as response:
                    data = response.read().decode("utf-8")
                return json.loads(data)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                time.sleep(min(2**attempt, 8))
        raise RuntimeError(f"FMP request failed: {last_error}")


def _safe_symbol(symbol: str) -> str:
    return symbol.replace("/", "_").replace("\\", "_").replace(":", "_")

