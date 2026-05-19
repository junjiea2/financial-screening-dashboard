# 四步排雷法：财务陷阱股票筛选器

这个小项目不会直接告诉你买什么，而是把明显有财务陷阱风险的公司先筛出来。规则引擎内部输出 `通过 / 警惕 / 排除 / 需专项分析`，网页展示层会把 `警惕` 显示为更温和的 `需关注`，表示“存在需要复核的单项风险”，不等同于危险公司。

## 项目目录

源码保留在项目根目录，数据产物已经归档到 `data/`：

- `data/universe/`：股票池与预筛股票池。
- `data/raw/`：原始财务采集结果。
- `data/normalized/`：标准化年度财务表。
- `data/screening/`：规则筛选和双轨结果，网页默认读取这里。
- `data/ai/`：AI 候选与 AI 评估结果。
- `data/reports/`：稳定性报告和实验摘要。
- `data/logs/`：长命令输出和耗时记录。
- `data/samples/`：示例 CSV。

更详细说明见 `docs/DATA_LAYOUT.md`。

## 快速运行

```powershell
python main.py
```

使用示例 CSV：

```powershell
python main.py --csv sample_financials.csv
```

导出结果：

```powershell
python main.py --csv sample_financials.csv --output result.csv
```

只看排除项：

```powershell
python main.py --csv sample_financials.csv --only 排除
```

获取尽可能大的股票池：

```powershell
python build_universe.py --markets US --output us_universe.csv
python build_universe.py --markets CN US --output stock_universe.csv
```

说明：`build_universe.py` 只负责抓“代码池”。完整财务筛选仍需要年度财务数据，建议先把数据清洗成下面的 CSV 字段后再跑 `main.py --csv ...`。美股代码池来自 Nasdaq Trader 当日 Symbol Directory；A 股代码池优先走 AkShare，网络被交易所/数据源重置时会失败，需要稍后重试或换数据源。

给股票池打行业模型标签：

```powershell
python classify_universe.py --input stock_universe.csv --output classified_universe.csv
```

预筛可投资 universe：

```powershell
python prefilter_universe.py --input classified_universe.csv --output investable_universe.csv --rejected-output rejected_universe.csv
python write_prefilter_report.py --investable investable_universe.csv --rejected rejected_universe.csv --output prefilter_report.txt
```

第一版预筛会过滤 ETF、权证、Units、Rights、优先股、SPAC/壳公司、ADR、A 股 ST/*ST、北交所/新三板类标的。市值、成交额、上市年限这类动态条件需要额外行情/上市日期数据，后续可接入后再做第二层预筛。

## 财务数据采集管道

不要一上来跑全量。建议按 20、500、全量三阶段推进：

```powershell
python fetch_us_financials.py --input classified_universe.csv --output us_financials_raw.csv --limit 20 --resume
python fetch_cn_financials.py --input classified_universe.csv --output cn_financials_raw.csv --limit 20 --resume
python normalize_financials.py --us us_financials_raw.csv --cn cn_financials_raw.csv --output full_financials.csv
python main.py --csv full_financials.csv --output screening_result.csv
```

小规模稳定后再扩大：

```powershell
python fetch_us_financials.py --input investable_universe.csv --output us_financials_raw.csv --limit 500 --resume
python fetch_cn_financials.py --input investable_universe.csv --output cn_financials_raw.csv --limit 500 --resume
```

建议分批跑 `500 -> 2000 -> 5000 -> 全量 investable_universe`。最后全量时去掉 `--limit`。两个采集脚本都会把失败原因写入 raw CSV，并支持 `--resume` 跳过已处理股票。

美股采集现在优先支持 Financial Modeling Prep：

```powershell
$env:FMP_API_KEY="你的FMP_KEY"
python fetch_us_financials.py --provider fmp --input classified_universe.csv --output us_financials_raw.csv --limit 20 --resume
```

也可以使用默认 `auto` 模式：有 `FMP_API_KEY` 时优先 FMP，没有 key 或 FMP 单只失败时回退到 `yfinance`。FMP 原始 JSON 会缓存到 `cache/us_financials/`，避免重复请求和浪费额度。

A 股第一版用 AkShare 财务摘要接口，当前优先拿营收、净利润、ROE、资产负债率等摘要字段，商誉、利息、完整现金流、分红等更适合后续接资产负债表/现金流量表专项接口补全。

当前 CN 市场的 `PE` 和 `PB` 多数为空，是因为 `fetch_cn_financials.py` 使用的是 AkShare 财务摘要接口，这个接口返回的是年报财务摘要，不包含实时或静态估值字段。A 股估值需要后续单独接行情/估值接口，再在标准化阶段补入 `pe`、`pb`。

可用下面的独立估值脚本补齐 A 股 `PE` / `PB`：

```powershell
python fetch_cn_valuations.py --input data/universe/investable_universe.csv --output data/raw/cn_valuations_raw.csv
python normalize_financials.py --us data/raw/us_financials_raw_investable_all.csv --cn data/raw/cn_financials_raw_investable_all.csv --cn-valuations data/raw/cn_valuations_raw.csv --output data/normalized/full_financials_investable_all.csv
```

`fetch_cn_valuations.py` 默认使用 `ak.stock_value_em(symbol)` 逐只股票读取当前 `PE(TTM)` 和 `市净率`，并按股票代码合并到标准化年度财务行。估值是当前快照，不是每个年报年度的历史估值。也可以用 `--provider spot-em` 尝试批量行情快照接口，但该接口更容易被数据源断开连接。

## 数据质量阈值

`data_quality.py` 会保留 `data_quality_score`，并按市场使用不同阈值：

```text
US:
  6年及以上：High
  3-5年：Medium
  1-2年：Low
  0年：Insufficient

CN/默认:
  8年及以上：High
  5-7年：Medium
  1-4年：Low
  0年：Insufficient
```

`Low` 和 `Insufficient` 会在最终结果中标为 `数据不足`。

网页端还会根据 `数据年数` 额外展示历史可信度：

```text
A 完整历史：>=10年
B 中等历史：5-9年
C 短历史：1-4年
未知：0年
```

当历史少于 10 年时，`10年ROE`、`ROE波动`、`5年营收CAGR` 等长期指标应理解为当前可用数据下的估计，并在人工复核时补充更长周期数据。

## SEC 研究路线

没有 FMP key 时，美股长期数据源应逐步切向 SEC/XBRL。当前研究笔记见 `SEC_RESEARCH.md`，建议路线是：

```text
Data Source Layer
↓
Raw Filing Layer
↓
Normalization Layer
↓
Quality Layer
↓
Industry Model Layer
↓
Risk Engine
↓
Explainable Screening
```

## CSV 字段

一行代表一只股票某一年的数据：

```text
symbol,market,name,industry,pe,pb,year,revenue,net_income,operating_cash_flow,shareholders_equity,total_assets,total_liabilities,capital_expenditure,goodwill,ebit,interest_expense,dividends_paid,non_performing_loan_ratio,solvency_ratio,duration_gap,net_gearing_ratio,roe
```

`roe` 可以为空，程序会用 `net_income / shareholders_equity` 估算。

第二版新增字段：

- `capital_expenditure`：资本开支，程序用 `经营现金流 - abs(资本开支)` 计算自由现金流。
- `goodwill`：商誉，用于计算商誉占总资产比例。
- `ebit` 和 `interest_expense`：用于计算利息覆盖倍数。
- `dividends_paid`：分红金额，用于判断近 5 年分红是否连续、是否明显下滑。
- `non_performing_loan_ratio`：银行不良率。
- `solvency_ratio` 和 `duration_gap`：保险偿付能力与久期缺口。
- `net_gearing_ratio`：地产净负债率。

## 四步规则

1. PB 低但长期亏损或经营现金流差，标记为排除。
2. 看 10 年数据，亏损年份过多排除，利润或 ROE 波动大则警惕。
3. 长期 ROE 低于 5% 排除；长期 ROE 低于 8% 且 PE 高于 10，标记为低回报陷阱。
4. 银行、保险、地产、券商、金融服务等高杠杆行业不直接通过，标记为需资产负债表专项分析。

第二版额外检查：

- 自由现金流：近 5 年多次为负则警惕。
- 资产负债率：普通公司超过阈值则警惕或排除，高杠杆行业单独处理。
- 商誉占比：商誉过高则警惕或排除。
- 利息覆盖倍数：过低说明偿债压力大。
- 分红稳定性：近 5 年分红不连续或明显下滑则警惕。
- 营收增长率：近 5 年营收 CAGR 明显为负则警惕或排除。

## 行业分类模型

程序现在会先把公司归到行业模型，再切换重点检查逻辑：

```text
银行：不良率、拨备覆盖、资本充足率
保险：偿付能力、久期缺口、投资收益质量
地产：净负债率、现金短债比、资产负债率
科技：营收增长、自由现金流、研发投入效率
消费：ROE、毛利率稳定性、分红稳定性
周期：利润波动、ROE波动、资本开支周期
金融：杠杆、资产质量、资本约束
通用：ROE、现金流、资产负债率
```

行业模型定义在 `industry_model.py`。现在是规则模型，后续可以接申万/中信/GICS 行业字段，让分类从关键词升级为标准行业映射。

双轨合并脚本 `merge_dual_track.py` 会把规则质量和 AI 评级放在一起观察。对于 `规则质量评级=优质候选` 且 `AI评级=优质候选`，但排雷结果因杠杆等单项指标进入 `需关注` 的公司，综合观察会保留质量判断，同时说明需要复核的风险点；消费行业高质量公司会被单独解释为“高质量消费公司需关注负债”的典型情形。

阈值集中在 `config.py`，可以按你的投资口径调整。

## 可选真实数据源

美股基础字段可以试用：

```powershell
pip install -r requirements.txt
python main.py --symbols AAPL MSFT
```

注意：`yfinance` 对完整 10 年财务口径支持不稳定。认真使用时，更建议把 Financial Modeling Prep、SEC、Tushare、AkShare 等数据清洗成 `sample_financials.csv` 这种年度表，再交给本筛选器统一打分。
