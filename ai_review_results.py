"""Optional AI review layer for screened stock results.

This script post-processes a screening_result CSV and adds concise AI review
columns. It intentionally runs after the deterministic rule engine so the core
screening remains cheap, reproducible, and usable without an API key.
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


AI_COLUMNS = ["AI判断", "AI置信度", "AI原因", "AI风险点", "AI复核模型"]
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
DEFAULT_DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEFAULT_PROVIDER = os.getenv("AI_PROVIDER", "deepseek")
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEEPSEEK_CHAT_URL = "https://api.deepseek.com/chat/completions"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add AI review columns to screening results.")
    parser.add_argument("--input", required=True, help="Input screening_result CSV.")
    parser.add_argument("--output", required=True, help="Output CSV with AI review columns.")
    parser.add_argument(
        "--only",
        default="通过",
        help="Only review rows with this deterministic result. Default: 通过.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum number of rows to call the API for. 0 means no limit.",
    )
    parser.add_argument(
        "--provider",
        choices=["deepseek", "openai"],
        default=DEFAULT_PROVIDER,
        help=f"AI provider. Default: {DEFAULT_PROVIDER}.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model name. Defaults to deepseek-chat for DeepSeek or gpt-4.1-mini for OpenAI.",
    )
    parser.add_argument(
        "--cache-dir",
        default="cache/ai_reviews",
        help="Local cache directory for AI review JSON.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.2,
        help="Seconds to sleep between API calls.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="If output exists, reuse existing AI review columns.",
    )
    return parser.parse_args()


def read_rows(path: str | Path) -> tuple[list[str], list[dict[str, str]]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = list(reader.fieldnames or [])
        return headers, list(reader)


def write_rows(path: str | Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def row_id(row: dict[str, str]) -> str:
    symbol = row.get("股票") or row.get("symbol") or "UNKNOWN"
    market = row.get("市场") or row.get("market") or "UNKNOWN"
    return f"{market}_{symbol}".replace("/", "_").replace("\\", "_")


def cache_key(row: dict[str, str], provider: str, model: str) -> str:
    stable_fields = {
        key: row.get(key, "")
        for key in [
            "股票",
            "市场",
            "名称",
            "行业",
            "行业模型",
            "核心指标",
            "PE",
            "PB",
            "10年ROE",
            "ROE波动",
            "5年平均FCF",
            "资产负债率",
            "商誉占比",
            "利息覆盖倍数",
            "分红稳定性",
            "5年营收CAGR",
            "数据年数",
            "数据质量分",
            "数据质量",
            "杠杆风险",
            "结果",
            "分数",
            "原因",
        ]
    }
    payload = json.dumps(
        {"provider": provider, "model": model, "row": stable_fields},
        ensure_ascii=False,
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{row_id(row)}_{digest}.json"


def prompt_for_row(row: dict[str, str]) -> str:
    fields = [
        "股票",
        "市场",
        "名称",
        "行业",
        "行业模型",
        "核心指标",
        "PE",
        "PB",
        "10年ROE",
        "ROE波动",
        "5年平均FCF",
        "资产负债率",
        "商誉占比",
        "利息覆盖倍数",
        "分红稳定性",
        "5年营收CAGR",
        "数据年数",
        "数据质量分",
        "数据质量",
        "杠杆风险",
        "结果",
        "分数",
        "原因",
    ]
    facts = "\n".join(f"- {field}: {row.get(field, '-')}" for field in fields)
    return f"""请作为保守的财务排雷复核助手，基于以下结构化指标复核这只股票。

要求：
1. 不要给出买入、卖出或目标价建议。
2. 只判断规则筛选结果是否看起来合理。
3. 如果规则结果为“通过”，也要说明为什么通过，以及还需要人工复核什么。
4. 结论必须短、可放进 CSV。

股票数据：
{facts}
"""


def system_prompt() -> str:
    return (
        "你是一个保守、可解释的股票财务排雷复核助手。"
        "你只基于用户提供的财务指标做二次复核，不提供买入、卖出、目标价或收益承诺。"
        "你必须返回严格 JSON，字段为 decision、confidence、reason、risks。"
        "decision 只能是：通过复核、谨慎通过、转为警惕、建议排除、数据不足。"
        "confidence 只能是：High、Medium、Low。"
        "reason 和 risks 都要适合放入 CSV，分别不超过 180 个中文字符。"
    )


def response_schema() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "name": "stock_ai_review",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "decision": {
                    "type": "string",
                    "enum": ["通过复核", "谨慎通过", "转为警惕", "建议排除", "数据不足"],
                },
                "confidence": {
                    "type": "string",
                    "enum": ["High", "Medium", "Low"],
                },
                "reason": {
                    "type": "string",
                    "maxLength": 180,
                },
                "risks": {
                    "type": "string",
                    "maxLength": 180,
                },
            },
            "required": ["decision", "confidence", "reason", "risks"],
        },
    }


def extract_text(data: dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    chunks: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str):
                chunks.append(text)
    return "".join(chunks)


def call_openai(row: dict[str, str], model: str, api_key: str) -> dict[str, str]:
    body = {
        "model": model,
        "instructions": (
            "你是一个保守、可解释的股票财务排雷复核助手。"
            "你只基于用户提供的财务指标做二次复核，不提供投资建议。"
        ),
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": prompt_for_row(row)}],
            }
        ],
        "text": {"format": response_schema()},
        "max_output_tokens": 450,
    }
    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
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
        raise RuntimeError(f"OpenAI API error {exc.code}: {detail}") from exc

    text = extract_text(data)
    parsed = json.loads(text)
    return {
        "AI判断": parsed["decision"],
        "AI置信度": parsed["confidence"],
        "AI原因": parsed["reason"],
        "AI风险点": parsed["risks"],
        "AI复核模型": model,
    }


def parse_json_text(text: str) -> dict[str, str]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    parsed = json.loads(stripped)
    return {
        "AI判断": str(parsed["decision"]),
        "AI置信度": str(parsed["confidence"]),
        "AI原因": str(parsed["reason"]),
        "AI风险点": str(parsed["risks"]),
    }


def call_deepseek(row: dict[str, str], model: str, api_key: str) -> dict[str, str]:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": prompt_for_row(row)},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
        "max_tokens": 450,
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
            raise RuntimeError(
                "DeepSeek API balance is insufficient. Please recharge or enable billing "
                "in the DeepSeek console, then rerun this command."
            ) from exc
        raise RuntimeError(f"DeepSeek API error {exc.code}: {detail}") from exc

    text = data["choices"][0]["message"]["content"]
    review = parse_json_text(text)
    review["AI复核模型"] = model
    return review


def call_ai(row: dict[str, str], provider: str, model: str, api_key: str) -> dict[str, str]:
    if provider == "deepseek":
        return call_deepseek(row, model, api_key)
    return call_openai(row, model, api_key)


def load_resume_rows(output_path: str | Path) -> dict[str, dict[str, str]]:
    path = Path(output_path)
    if not path.exists():
        return {}
    _, rows = read_rows(path)
    return {row_id(row): row for row in rows if row.get("AI判断")}


def main() -> None:
    args = parse_args()
    provider = args.provider
    model = args.model or (DEFAULT_DEEPSEEK_MODEL if provider == "deepseek" else DEFAULT_MODEL)
    key_env = "DEEPSEEK_API_KEY" if provider == "deepseek" else "OPENAI_API_KEY"
    api_key = os.getenv(key_env)
    if not api_key:
        raise SystemExit(
            f"{key_env} is not set. Set it first in the current shell, "
            f"for example: $env:{key_env}='sk-...'"
        )

    headers, rows = read_rows(args.input)
    output_headers = headers + [column for column in AI_COLUMNS if column not in headers]
    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    resumed = load_resume_rows(args.output) if args.resume else {}

    calls = 0
    reviewed = 0
    for index, row in enumerate(rows, start=1):
        existing = resumed.get(row_id(row))
        if existing:
            for column in AI_COLUMNS:
                row[column] = existing.get(column, "")
            continue

        if row.get("结果") != args.only:
            for column in AI_COLUMNS:
                row.setdefault(column, "")
            continue

        if args.limit and reviewed >= args.limit:
            for column in AI_COLUMNS:
                row.setdefault(column, "")
            continue

        cache_path = cache_dir / cache_key(row, provider, model)
        if cache_path.exists():
            review = json.loads(cache_path.read_text(encoding="utf-8"))
        else:
            review = call_ai(row, provider, model, api_key)
            cache_path.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
            calls += 1
            if args.sleep > 0:
                time.sleep(args.sleep)

        row.update(review)
        reviewed += 1
        print(f"[AI] {index}/{len(rows)} {row_id(row)}: {row.get('AI判断')}")

    write_rows(args.output, output_headers, rows)
    print(
        f"Wrote AI-reviewed results to {args.output}; provider: {provider}; "
        f"model: {model}; reviewed rows: {reviewed}; API calls: {calls}"
    )


if __name__ == "__main__":
    main()
