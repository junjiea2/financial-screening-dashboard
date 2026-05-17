"""CLI entry point for the four-step financial minefield screener."""

from __future__ import annotations

import argparse

from data_loader import load_from_csv, load_from_yfinance, load_sample_universe
from filters import screen_universe
from output import print_table, write_csv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="四步排雷法：财务陷阱股票筛选器"
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--csv", help="读取本地股票财务CSV，一行一只股票的一年数据")
    source.add_argument(
        "--symbols",
        nargs="+",
        help="用yfinance读取美股基础行情字段，例如: --symbols AAPL MSFT",
    )
    parser.add_argument(
        "--output",
        help="可选：把筛选结果写入CSV文件",
    )
    parser.add_argument(
        "--only",
        choices=["通过", "警惕", "排除", "需专项分析", "数据不足"],
        help="只显示某一种结果",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.csv:
        stocks = load_from_csv(args.csv)
    elif args.symbols:
        stocks = load_from_yfinance(args.symbols)
    else:
        stocks = load_sample_universe()

    results = screen_universe(stocks)
    if args.only:
        results = [result for result in results if result.result == args.only]

    print_table(results)
    if args.output:
        write_csv(results, args.output)


if __name__ == "__main__":
    main()
