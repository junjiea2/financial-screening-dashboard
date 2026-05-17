"""Basic smoke tests for the screener."""

from data_loader import load_from_csv, load_sample_universe
from data_quality import score_data_quality
from filters import screen_stock, screen_universe
from indicators import revenue_cagr
from models import FinancialRecord, StockFinancials


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


if __name__ == "__main__":
    test_sample_results()
    test_csv_loader()
    test_us_quality_thresholds()
    test_medium_quality_is_degraded_not_blocked()
    test_revenue_cagr_ignores_negative_endpoint()
    print("All tests passed.")
