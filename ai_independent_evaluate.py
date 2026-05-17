"""AI-only stock quality evaluation from normalized financial records.

This script does not read or use the deterministic four-step screening result.
It summarizes normalized annual financials and asks an AI model to classify each
stock's quality and potential for further research.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from data_loader import load_from_csv
from data_quality import score_data_quality
from indicators import (
    coefficient_of_variation,
    count_negative,
    dividend_stability,
    free_cash_flow,
    infer_roe,
    latest_asset_liability_ratio,
    latest_goodwill_ratio,
    latest_interest_coverage,
    last_n_records,
    revenue_cagr,
    safe_mean,
    sample_std,
)
from models import StockFinancials


DEEPSEEK_CHAT_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
HEADERS = [
    "股票",
    "市场",
    "名称",
    "行业",
    "数据年数",
    "数据质量分",
    "数据质量",
    "10年ROE",
    "ROE波动",
    "净利润波动",
    "近5年亏损次数",
    "近5年OCF为负次数",
    "5年平均FCF",
    "资产负债率",
    "商誉占比",
    "利息覆盖倍数",
    "分红稳定性",
    "5年营收CAGR",
    "AI评级",
    "AI置信度",
    "AI理由",
    "AI风险",
    "AI关注点",
    "AI模型",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI-only stock quality evaluation.")
    parser.add_argument("--input", required=True, help="Normalized financial CSV.")
    parser.add_argument("--output", required=True, help="Output AI evaluation CSV.")
    parser.add_argument("--market", default="", help="Optional market filter, e.g. CN.")
    parser.add_argument("--limit", type=int, default=0, help="Max stocks to evaluate.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"DeepSeek model. Default: {DEFAULT_MODEL}.")
    parser.add_argument("--cache-dir", default="cache/ai_independent_reviews")
    parser.add_argument("--sleep", type=float, default=0.2)
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def fmt_percent(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value * 100:.1f}%"


def fmt_number(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}"


def summarize(stock: StockFinancials) -> dict[str, str]:
    five_year = last_n_records(stock.records, 5)
    ten_year = last_n_records(stock.records, 10)
    ten_year_roe = [infer_roe(record) for record in ten_year]
    ten_year_net_income = [record.net_income for record in ten_year]
    five_year_net_income = [record.net_income for record in five_year]
    five_year_ocf = [record.operating_cash_flow for record in five_year]
    five_year_fcf = [free_cash_flow(record) for record in five_year]
    dividend_status, _ = dividend_stability(stock.records, 5)
    data_years, _, quality_score, quality_level = score_data_quality(stock.records, stock.market)
    return {
        "股票": stock.symbol,
        "市场": stock.market,
        "名称": stock.name or "-",
        "行业": stock.industry or "-",
        "数据年数": str(data_years),
        "数据质量分": str(quality_score),
        "数据质量": quality_level,
        "10年ROE": fmt_percent(safe_mean(ten_year_roe)),
        "ROE波动": fmt_percent(sample_std(ten_year_roe)),
        "净利润波动": fmt_number(coefficient_of_variation(ten_year_net_income)),
        "近5年亏损次数": str(count_negative(five_year_net_income)),
        "近5年OCF为负次数": str(count_negative(five_year_ocf)),
        "5年平均FCF": fmt_number(safe_mean(five_year_fcf)),
        "资产负债率": fmt_percent(latest_asset_liability_ratio(stock.records)),
        "商誉占比": fmt_percent(latest_goodwill_ratio(stock.records)),
        "利息覆盖倍数": fmt_number(latest_interest_coverage(stock.records)),
        "分红稳定性": dividend_status,
        "5年营收CAGR": fmt_percent(revenue_cagr(stock.records, 5)),
    }


def cache_key(row: dict[str, str], model: str) -> str:
    payload = json.dumps({"model": model, "row": row}, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{row['市场']}_{row['股票']}_{digest}.json".replace("/", "_").replace("\\", "_")


def system_prompt() -> str:
    return (
        "你是保守的股票质量评估助手。你不使用任何外部行情或新闻，只基于用户给出的财务摘要。"
        "你的目标不是降低通过率，而是找出真正值得继续研究的优质候选。"
        "不要给买入、卖出、目标价或收益承诺。必须返回严格 JSON。"
    )


def user_prompt(row: dict[str, str]) -> str:
    facts = "\n".join(f"- {key}: {value}" for key, value in row.items())
    return f"""请独立评估这只股票的质量和继续研究价值，不要参考四步排雷结论。

评级只能五选一：
- 优质候选：财务质量、稳定性、增长或现金流明显较好，值得优先研究
- 可跟踪：没有明显硬伤，但质量或增长还不够突出
- 谨慎观察：存在一项以上重要风险，需要更多数据验证
- 排除：财务质量明显较弱或风险较高
- 数据不足：关键数据不足以判断

请返回 JSON：
{{
  "rating": "...",
  "confidence": "High/Medium/Low",
  "reason": "不超过180字",
  "risks": "不超过180字",
  "watch_items": "不超过160字"
}}

财务摘要：
{facts}
"""


def parse_json_text(text: str) -> dict[str, str]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`").strip()
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    parsed = json.loads(stripped)
    return {
        "AI评级": str(parsed["rating"]),
        "AI置信度": str(parsed["confidence"]),
        "AI理由": str(parsed["reason"]),
        "AI风险": str(parsed["risks"]),
        "AI关注点": str(parsed["watch_items"]),
    }


def call_deepseek(row: dict[str, str], model: str, api_key: str) -> dict[str, str]:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": user_prompt(row)},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
        "max_tokens": 500,
        "stream": False,
    }
    request = urllib.request.Request(
        DEEPSEEK_CHAT_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if exc.code == 402 or "Insufficient Balance" in detail:
            raise RuntimeError("DeepSeek API balance is insufficient.") from exc
        raise RuntimeError(f"DeepSeek API error {exc.code}: {detail}") from exc
    review = parse_json_text(data["choices"][0]["message"]["content"])
    review["AI模型"] = model
    return review


def load_existing(path: str | Path) -> dict[str, dict[str, str]]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {
            f"{row['市场']}_{row['股票']}": row
            for row in csv.DictReader(handle)
            if row.get("AI评级")
        }


def write_rows(path: str | Path, rows: list[dict[str, str]]) -> None:
    with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise SystemExit("DEEPSEEK_API_KEY is not set in this shell.")

    stocks = load_from_csv(args.input)
    if args.market:
        stocks = [stock for stock in stocks if stock.market.upper() == args.market.upper()]
    if args.limit:
        stocks = stocks[: args.limit]

    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    existing = load_existing(args.output) if args.resume else {}
    rows: list[dict[str, str]] = []
    calls = 0

    for index, stock in enumerate(stocks, start=1):
        row = summarize(stock)
        identity = f"{row['市场']}_{row['股票']}"
        if identity in existing:
            row.update({key: existing[identity].get(key, "") for key in HEADERS})
            rows.append(row)
            continue

        cache_path = cache_dir / cache_key(row, args.model)
        if cache_path.exists():
            review = json.loads(cache_path.read_text(encoding="utf-8"))
        else:
            review = call_deepseek(row, args.model, api_key)
            cache_path.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
            calls += 1
            if args.sleep > 0:
                time.sleep(args.sleep)
        row.update(review)
        rows.append(row)
        print(f"[AI独立] {index}/{len(stocks)} {identity}: {row.get('AI评级')}")

    write_rows(args.output, rows)
    print(f"Wrote {len(rows)} AI-only evaluations to {args.output}; API calls: {calls}")


if __name__ == "__main__":
    main()
