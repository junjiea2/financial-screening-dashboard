# 数据目录说明

项目根目录保留 Python 源码、`README.md`、`requirements.txt` 和 `dashboard/`。

数据产物统一放在 `data/`：

- `data/universe/`：股票池、分类股票池、可投股票池、剔除股票池。
- `data/raw/`：美股和 A 股原始财务采集结果。
- `data/normalized/`：统一字段后的年度财务表。
- `data/screening/`：规则筛选、双轨合并、网页默认读取的结果表。
- `data/ai/`：AI 候选池、AI 独立评估结果、中间批次。
- `data/reports/`：稳定性报告、预筛报告、实验摘要。
- `data/logs/`：长命令控制台输出、采集耗时记录。
- `data/samples/`：小样本和示例 CSV。

辅助运行脚本放在 `scripts/`，研究文档放在 `docs/`。

网页端默认读取：

```text
data/screening/dual_track_investable_all_ai_quality_all.csv
```

常用命令示例：

```powershell
python main.py --csv data/normalized/full_financials_investable_all.csv --output data/screening/screening_result_investable_all_rules.csv

python normalize_financials.py `
  --us data/raw/us_financials_raw_investable_all.csv `
  --cn data/raw/cn_financials_raw_investable_all.csv `
  --output data/normalized/full_financials_investable_all.csv
```
