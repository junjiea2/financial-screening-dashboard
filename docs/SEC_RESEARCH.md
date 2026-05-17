# SEC / XBRL Parser Research

目标：在没有 FMP key 的情况下，为美股建立更深的 fundamentals 数据源，让系统逐步从 `yfinance` 过渡到 SEC 原始披露数据。

## 结论

短期优先路线：

1. 使用 SEC 官方 `data.sec.gov` APIs 获取 CIK、filing metadata 和 Company Facts JSON。
2. 从 Company Facts 中抽取标准 `us-gaap` 指标，先覆盖收入、净利润、资产、负债、权益、经营现金流、资本开支、商誉等核心字段。
3. 对 Company Facts 缺失或口径冲突的公司，再下载 10-K filing / inline XBRL 原文解析。

不建议第一步直接手写完整 XBRL parser。XBRL 口径、context、duration/instant、单位、amendment、company-specific tags 都会带来复杂度，应先用官方聚合 JSON 建立可用基线。

## 候选方案

### 1. SEC 官方 data APIs

用途：

- `submissions`：按 CIK 获取公司 filing metadata。
- `companyfacts`：按 CIK 获取 XBRL facts JSON。
- `companyconcept`：按公司和概念获取单个指标历史。

优点：

- 官方、免费、稳定。
- 直接 JSON，无需先解析 HTML/iXBRL。
- 很适合做 Raw Filing Layer 的第一版。

风险：

- 并非所有 XBRL facts 都完整映射到常用字段。
- 需要 ticker -> CIK 映射。
- 需要严格遵守 SEC fair access，需要明确 User-Agent 和限流。

### 2. sec-edgar-downloader

用途：

- 下载 10-K / 10-Q / 8-K 原始 filing。
- 适合作为 Raw Filing Layer 的下载器。

优点：

- 包成熟，当前 PyPI 版本 5.1.0。
- 支持按 ticker 或 CIK 下载。
- 初始化时要求 company name + email 形成 SEC 需要的 User-Agent。

风险：

- 它解决“下载”，不解决“标准化财务字段”。
- 后面仍需要 XBRL/iXBRL parser。

### 3. EdgarTools

用途：

- 从 SEC filing 中解析 XBRL。
- 提供 income statement、balance sheet、cash flow 等 statement 访问。

优点：

- 抽象层更接近本项目需要。
- 支持 statement standardization、多期拼接、facts query。

风险：

- 要先验证它对小盘股、ADR、SPAC 的表现。
- 需要评估性能和缓存策略。

### 4. py-xbrl / xbrl-core

用途：

- 更底层的 XBRL/iXBRL 文件解析。

优点：

- 能处理原始 XBRL 文档，控制力强。

风险：

- 标准化负担会落回我们自己身上。
- 更适合作为第三阶段 fallback，而不是第一阶段。

### 5. sec-api

用途：

- 商业 API，可提供 filing search、XBRL-to-JSON 等能力。

优点：

- 工程成本低。

风险：

- 需要 key 和额度；目前项目已经明确无 FMP key，因此也不宜把 sec-api 当主路线。

## 建议架构

```text
Data Source Layer
  SEC data APIs
  yfinance fallback
  AkShare

Raw Filing Layer
  cache/sec/companyfacts/{CIK}.json
  cache/sec/submissions/{CIK}.json
  cache/sec/filings/{CIK}/{accession}/

Normalization Layer
  normalize_sec_companyfacts.py
  normalize_financials.py

Quality Layer
  data_quality.py
  market-specific thresholds

Industry Model Layer
  industry_model.py

Risk Engine
  filters.py

Explainable Screening
  output.py
  dashboard/
```

## SEC 字段映射初稿

标准 schema 字段 -> SEC us-gaap concepts：

```text
revenue:
  Revenues
  RevenueFromContractWithCustomerExcludingAssessedTax
  SalesRevenueNet

net_income:
  NetIncomeLoss
  ProfitLoss

operating_cash_flow:
  NetCashProvidedByUsedInOperatingActivities

capital_expenditure:
  PaymentsToAcquirePropertyPlantAndEquipment

free_cash_flow:
  operating_cash_flow - abs(capital_expenditure)

total_assets:
  Assets

total_liabilities:
  Liabilities

shareholders_equity:
  StockholdersEquity
  StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest

goodwill:
  Goodwill

interest_expense:
  InterestExpenseNonOperating
  InterestExpense

dividends_paid:
  PaymentsOfDividends
  PaymentsOfDividendsCommonStock
```

## 下一步实现建议

1. 新建 `sec_client.py`：
   - User-Agent 从环境变量读取，例如 `SEC_USER_AGENT`。
   - 支持 ticker -> CIK 映射。
   - 缓存 `companyfacts` 和 `submissions`。

2. 新建 `fetch_us_financials_sec.py` 或扩展 `fetch_us_financials.py --provider sec`：
   - 对 US 普通股拉 companyfacts。
   - 按 fiscal year 聚合 10 年 annual facts。
   - 输出当前 raw CSV schema。

3. 数据质量目标：
   - US `Medium` 不低于 70%。
   - US `High` 逐步提升，但不要为了分数牺牲字段准确性。

4. 再研究 raw filing XBRL：
   - 若 companyfacts 缺关键字段，再用 `sec-edgar-downloader` 下载 10-K。
   - 评估 EdgarTools 是否能直接输出标准三表。

## 参考来源

- SEC data APIs: https://data.sec.gov/
- SEC API documentation入口: https://www.sec.gov/edgar/sec-api-documentation
- SEC developer / fair access: https://www.sec.gov/developer
- sec-edgar-downloader: https://pypi.org/project/sec-edgar-downloader/
- EdgarTools XBRL docs: https://edgartools.readthedocs.io/en/stable/api/xbrl/
- py-xbrl: https://pypi.org/project/py-xbrl/

