"""Basic smoke tests for the screener."""

from data_loader import load_from_csv, load_sample_universe
from data_quality import score_data_quality
from evaluate_calibration import evaluate_case
from filters import screen_stock, screen_universe
from indicators import revenue_cagr
from merge_dual_track import disagreement
from merge_multi_ai_reviews import merge_reviews
from models import FinancialRecord, StockFinancials
from normalize_financials import _valuation_map
from quality_pool_rank import build_quality_pool


def test_sample_results() -> None:
    results = {item.symbol: item for item in screen_universe(load_sample_universe())}
    assert results["AAPL"].result == "通过"
    assert results["AAPL"].data_quality_level == "High"
    assert results["AAPL"].avg_free_cash_flow_5y is not None
    assert results["AAPL"].dividend_stability == "稳定"
    assert results["LOWPB"].result == "排除"
    assert results["BANKX"].result == "需专项分析"
    assert results["CYCL"].result == "警惕"
    assert results["CYCL"].dividend_stability == "不连续"


def test_csv_loader() -> None:
    stocks = load_from_csv("data/samples/sample_financials.csv")
    assert len(stocks) == 4
    assert len(stocks[0].records) == 10


def test_us_quality_thresholds() -> None:
    records = [
        FinancialRecord(
            year=2020 + index,
            revenue=100,
            net_income=10,
            shareholders_equity=50,
            asset_liability_ratio=0.4,
        )
        for index in range(4)
    ]
    assert score_data_quality(records, "US")[3] == "Medium"
    assert score_data_quality(records, "CN")[3] == "Low"


def test_medium_quality_is_degraded_not_blocked() -> None:
    records = [
        FinancialRecord(
            year=2020 + index,
            revenue=100 + index * 10,
            net_income=20 + index,
            operating_cash_flow=30 + index,
            shareholders_equity=80,
            asset_liability_ratio=0.35,
            total_assets=120,
            total_liabilities=40,
            roe=0.20,
        )
        for index in range(4)
    ]
    result = screen_stock(
        StockFinancials(
            symbol="MED",
            market="US",
            name="Medium Quality",
            industry="Software",
            pe=20,
            pb=4,
            records=records,
        )
    )
    assert result.data_quality_level == "Medium"
    assert result.result == "通过"
    assert result.score == 85
    assert any("置信度中等" in flag for flag in result.flags)


def test_revenue_cagr_ignores_negative_endpoint() -> None:
    records = [
        FinancialRecord(year=2021, revenue=100),
        FinancialRecord(year=2022, revenue=120),
        FinancialRecord(year=2023, revenue=-10),
    ]
    assert revenue_cagr(records, 3) is None


def test_high_quality_warn_gets_contextual_observation() -> None:
    rule_row = {
        "结果": "警惕",
        "规则质量评级": "优质候选",
        "行业模型": "消费",
        "杠杆风险": "中",
        "数据年数": "4",
    }
    ai_row = {"AI评级": "优质候选"}
    split, observation = disagreement(rule_row, ai_row)
    assert split == "否"
    assert "高质量消费公司需关注负债" in observation
    assert "短历史估计" in observation


def test_cn_valuation_map_reads_pe_pb() -> None:
    from pathlib import Path
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "valuations.csv"
        path.write_text(
            "symbol,market,name,pe,pb,source,status,error\n"
            "000001,CN,平安银行,5.2,0.6,akshare,ok,\n"
            "000002,CN,万科A,,,akshare,ok,\n",
            encoding="utf-8-sig",
        )
        valuations = _valuation_map(str(path))
    assert valuations["000001"] == {"pe": "5.2", "pb": "0.6"}
    assert "000002" not in valuations


def test_quality_pool_ranks_any_positive_signal() -> None:
    rows = [
        {
            "股票": "AAA",
            "市场": "US",
            "结果": "通过",
            "分数": "100",
            "规则质量评级": "优质候选",
            "规则质量分": "95",
            "AI评级": "优质候选",
            "数据质量分": "100",
            "数据质量": "High",
            "数据年数": "10",
            "10年ROE": "20%",
            "ROE波动": "3%",
            "5年平均FCF": "100",
            "资产负债率": "25%",
            "5年营收CAGR": "8%",
            "PE": "18",
            "PB": "3",
            "规则AI分歧": "否",
        },
        {
            "股票": "BBB",
            "市场": "US",
            "结果": "排除",
            "分数": "0",
            "规则质量评级": "排除",
            "规则质量分": "20",
            "AI评级": "",
        },
    ]
    pool = build_quality_pool(rows)
    assert [row["股票"] for row in pool] == ["AAA"]
    assert pool[0]["优质池等级"] == "核心优质池"
    assert "规则通过" in pool[0]["入选来源"]


def test_multi_ai_consensus_detects_disagreement() -> None:
    groups = {
        ("US", "XYZ"): [
            ("deepseek", {"市场": "US", "股票": "XYZ", "名称": "Example", "AI评级": "优质候选"}),
            ("openai", {"市场": "US", "股票": "XYZ", "名称": "Example", "AI评级": "排除"}),
        ]
    }
    merged = merge_reviews(groups)
    assert merged[0]["AI复核模型数"] == "2"
    assert merged[0]["AI分歧状态"] == "明显分歧"
    assert "deepseek:优质候选" in merged[0]["AI评级明细"]


def test_calibration_high_quality_requires_expected_pool_level() -> None:
    report = evaluate_case(
        {"股票": "AAA", "市场": "US", "预期类别": "高质量", "最低优质池等级": "优质池", "允许结果": "通过|警惕"},
        {"股票": "AAA", "市场": "US", "结果": "通过", "规则质量评级": "优质候选", "AI评级": "优质候选"},
        {"股票": "AAA", "市场": "US", "优质池等级": "核心优质池"},
    )
    assert report["校准通过"] == "是"

    weak_report = evaluate_case(
        {"股票": "AAA", "市场": "US", "预期类别": "高质量", "最低优质池等级": "优质池", "允许结果": "通过|警惕"},
        {"股票": "AAA", "市场": "US", "结果": "通过", "规则质量评级": "优质候选", "AI评级": "优质候选"},
        {"股票": "AAA", "市场": "US", "优质池等级": "观察池"},
    )
    assert weak_report["校准通过"] == "否"
    assert "低于最低预期" in weak_report["失败原因"]


def test_calibration_blocks_high_risk_core_pool() -> None:
    report = evaluate_case(
        {"股票": "BAD", "市场": "US", "预期类别": "高风险", "禁止优质池等级": "核心优质池|优质池"},
        {"股票": "BAD", "市场": "US", "结果": "排除", "规则质量评级": "排除", "AI评级": ""},
        {"股票": "BAD", "市场": "US", "优质池等级": "核心优质池"},
    )
    assert report["校准通过"] == "否"
    assert "高风险样本进入核心优质池" in report["失败原因"]


def test_calibration_missing_high_quality_stock_fails() -> None:
    report = evaluate_case(
        {"股票": "MISSING", "市场": "US", "预期类别": "高质量", "最低优质池等级": "可研究池"},
        None,
        None,
    )
    assert report["校准通过"] == "否"
    assert "筛选结果缺失" in report["失败原因"]


if __name__ == "__main__":
    test_sample_results()
    test_csv_loader()
    test_us_quality_thresholds()
    test_medium_quality_is_degraded_not_blocked()
    test_revenue_cagr_ignores_negative_endpoint()
    test_high_quality_warn_gets_contextual_observation()
    test_cn_valuation_map_reads_pe_pb()
    test_quality_pool_ranks_any_positive_signal()
    test_multi_ai_consensus_detects_disagreement()
    test_calibration_high_quality_requires_expected_pool_level()
    test_calibration_blocks_high_risk_core_pool()
    test_calibration_missing_high_quality_stock_fails()
    print("All tests passed.")
