const DATASETS = [
  {
    label: "10496只全量 v2 规则版（无AI）",
    url: "./data/screening/investment_screen_v2_investable_all_summary.csv",
    format: "v2_summary",
    reportUrl: "./data/reports/investment_screen_v2_investable_all_manifest.json",
    reportFormat: "v2_manifest",
    defaultSort: { key: "规则质量分", direction: "desc" },
  },
  {
    label: "优质池排序（任一轨道看好）",
    url: "./data/screening/quality_pool_investable_all.csv",
    reportUrl: "./data/reports/stability_report_investable_all.txt",
  },
  {
    label: "10496只全量双轨 + AI候选全覆盖",
    url: "./data/screening/dual_track_investable_all_ai_quality_all.csv",
    reportUrl: "./data/reports/stability_report_investable_all.txt",
  },
  {
    label: "10496只全量双轨 + AI1700",
    url: "./data/screening/dual_track_investable_all_ai1700.csv",
    reportUrl: "./data/reports/stability_report_investable_all.txt",
  },
  {
    label: "10496只全量双轨 + AI1000",
    url: "./data/screening/dual_track_investable_all_ai1000.csv",
    reportUrl: "./data/reports/stability_report_investable_all.txt",
  },
  {
    label: "10496只全量双轨 + AI500",
    url: "./data/screening/dual_track_investable_all_ai500.csv",
    reportUrl: "./data/reports/stability_report_investable_all.txt",
  },
  {
    label: "10496只全量双轨 + AI200",
    url: "./data/screening/dual_track_investable_all_ai200.csv",
    reportUrl: "./data/reports/stability_report_investable_all.txt",
  },
  {
    label: "10496只全量可投规则单轨",
    url: "./data/screening/screening_result_investable_all_rules.csv",
    reportUrl: "./data/reports/stability_report_investable_all.txt",
  },
  {
    label: "3913只双轨 + AI200",
    url: "./data/screening/dual_track_investable_2000_ai200.csv",
    reportUrl: "./data/reports/stability_report_investable_2000.txt",
  },
  {
    label: "3913只双轨 + AI100",
    url: "./data/screening/dual_track_investable_2000_ai100.csv",
    reportUrl: "./data/reports/stability_report_investable_2000.txt",
  },
  {
    label: "100只A股双轨样本",
    url: "./data/screening/dual_track_cn_100.csv",
    reportUrl: "./data/reports/stability_report_investable_2000.txt",
  },
  {
    label: "3913只规则双轨",
    url: "./data/screening/screening_result_investable_2000_dual_rules.csv",
    reportUrl: "./data/reports/stability_report_investable_2000.txt",
  },
  {
    label: "3913只旧版筛选",
    url: "./data/screening/screening_result_investable_2000.csv",
    reportUrl: "./data/reports/stability_report_investable_2000.txt",
  },
  {
    label: "500只稳定性测试",
    url: "./data/screening/screening_result_investable_500.csv",
    reportUrl: "./data/reports/stability_report_investable_500.txt",
  },
];

let rows = [];
let filteredRows = [];
let sortState = { key: "分数", direction: "asc" };
let detailRows = [];
let activeTrait = null;
let currentPage = 1;
let pageSize = 100;
let filterTimer = null;

const traitFilters = {
  highRoe: {
    label: "10年ROE >= 15%",
    match: (row) => asNumber(row["10年ROE"]) >= 15,
  },
  lowDebt: {
    label: "资产负债率 <= 30%",
    match: (row) => asNumber(row["资产负债率"]) <= 30,
  },
  highDebt: {
    label: "资产负债率 >= 60%",
    match: (row) => asNumber(row["资产负债率"]) >= 60,
  },
  ruleAiQuality: {
    label: "规则与AI都为优质候选",
    match: (row) => row["规则质量评级"] === "优质候选" && row["AI评级"] === "优质候选",
  },
};

const baseColumns = [
  "股票",
  "市场",
  "名称",
  "行业模型",
  "PE",
  "PB",
  "10年ROE",
  "资产负债率",
  "数据年数",
  "历史可信度",
  "数据质量分",
  "数据质量",
  "结果",
  "分数",
  "规则质量评级",
  "规则质量分",
  "AI评级",
  "规则AI分歧",
  "详情",
];

const optionalColumns = [
  "综合优质分",
  "优质池等级",
  "行业相对质量分",
  "资本效率分",
  "行业因子模型",
  "入选来源",
  "v2风险状态",
  "v2当前趋势",
  "v2估值状态",
  "v2估值置信度",
  "v2策略池",
  "v2池资格",
  "v2年报as-of",
  "v2季度as-of",
  "v2价格as-of",
  "v2证据状态",
  "v2质量置信度",
  "v2可评分权重",
  "v2排名资格",
  "v2池内排名",
];

const columnHelp = {
  数据质量分:
    "衡量财务数据本身是否够完整。先统计可用完整年度：收入、净利润、ROE或股东权益、资产负债表锚点都具备才算完整年度。US：6年及以上为High，3-5年为Medium；CN：8年及以上为High，5-7年为Medium。分数按完整年度折算，数据不足会降为0。",
  规则质量分:
    "衡量公司财务质量，不等同于排雷结果。基础分45；数据质量High加5；ROE达到行业优秀线加22、基本线加8，低于基本线扣10；ROE稳定加8，波动或利润波动会扣分；近5年无亏损加6；经营现金流持续为正加12；自由现金流整体为正加6；资产负债率、营收增长按行业模型加减分。最后限制在0-100，并映射为优质候选、可跟踪、谨慎观察或排除。",
  行业相对质量分:
    "把股票放回同市场、同行业模型中比较。参考MSCI/S&P质量因子，按行业侧重盈利、稳定、杠杆、现金流、成长和估值。样本不足时退到同市场或全局分位数。",
  资本效率分:
    "判断高ROE是否有现金含量、是否依赖杠杆。当前用现金转换率、FCF/净利润、ROA或近似ROA、杠杆依赖度综合评估；缺少字段时会保守降为近似判断。",
};

const columnWidths = {
  股票: "92px",
  市场: "58px",
  名称: "250px",
  行业模型: "88px",
  PE: "70px",
  PB: "70px",
  "10年ROE": "96px",
  资产负债率: "110px",
  数据年数: "96px",
  历史可信度: "126px",
  数据质量分: "118px",
  数据质量: "108px",
  结果: "100px",
  分数: "72px",
  综合优质分: "110px",
  优质池等级: "112px",
  行业相对质量分: "132px",
  资本效率分: "112px",
  行业因子模型: "136px",
  入选来源: "180px",
  v2风险状态: "112px",
  v2当前趋势: "112px",
  v2估值状态: "112px",
  v2估值置信度: "112px",
  v2策略池: "120px",
  v2池资格: "96px",
  "v2年报as-of": "120px",
  "v2季度as-of": "120px",
  "v2价格as-of": "120px",
  v2证据状态: "112px",
  v2质量置信度: "112px",
  v2可评分权重: "112px",
  v2排名资格: "112px",
  v2池内排名: "104px",
  规则质量评级: "126px",
  规则质量分: "118px",
  AI评级: "110px",
  规则AI分歧: "112px",
  详情: "72px",
};

function resultDisplayLabel(value) {
  if (value === "警惕") return "需关注";
  return value || "-";
}

function historyConfidence(row) {
  const years = Number(row["数据年数"] || 0);
  if (years >= 10) return "A 完整历史";
  if (years >= 5) return "B 中等历史";
  if (years > 0) return "C 短历史";
  return "未知";
}

function historyConfidenceNote(row) {
  const years = Number(row["数据年数"] || 0);
  if (years >= 10) return "已覆盖 10 年口径，长期 ROE 与波动统计可信度较高。";
  if (years >= 5) return "覆盖 5-9 年，适合初筛，但长期质量结论仍需补充历史。";
  if (years > 0) return "少于 5 年，10年ROE、ROE波动和CAGR应视为短历史估计。";
  return "缺少可用年度数据。";
}

function parseCsv(text) {
  const output = [];
  let row = [];
  let cell = "";
  let quoted = false;

  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    const next = text[i + 1];
    if (char === '"' && quoted && next === '"') {
      cell += '"';
      i += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === "," && !quoted) {
      row.push(cell);
      cell = "";
    } else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && next === "\n") i += 1;
      row.push(cell);
      if (row.some((value) => value !== "")) output.push(row);
      row = [];
      cell = "";
    } else {
      cell += char;
    }
  }
  if (cell || row.length) {
    row.push(cell);
    output.push(row);
  }
  const headers = output.shift();
  return output.map((values) =>
    Object.fromEntries(headers.map((header, index) => [header, values[index] ?? ""]))
  );
}

function asNumber(value) {
  if (!value || value === "-") return Number.NaN;
  return Number(String(value).replace("%", ""));
}

function prepareRows(items) {
  return items.map((row) => {
    const searchText = [
      row["股票"],
      row["名称"],
      row["行业"],
      row["行业模型"],
      row["原因"],
      row["质量理由"],
      row["AI原因"],
      row["AI风险点"],
      row["AI理由"],
      row["AI风险"],
      row["AI关注点"],
      row["AI护城河等级"],
      row["AI护城河类型"],
      row["AI护城河证据"],
      row["AI护城河反证"],
      row["AI证据等级"],
      row["AI定价权判断"],
      row["AI客户粘性判断"],
      row["AI竞争强度判断"],
      row["AI资本效率判断"],
      row["AI管理层资本配置"],
      row["AI领导人与文化证据"],
      row["AI管理层文化观察"],
      row["AI外部验证需求"],
      row["AI护城河方法来源"],
      row["行业相对理由"],
      row["资本效率理由"],
      row["综合观察"],
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return {
      ...row,
      "展示结果": resultDisplayLabel(row["结果"]),
      "历史可信度": historyConfidence(row),
      _searchText: searchText,
      _score: Number(row["分数"] || 0),
      _aiReviewed: Boolean(row["AI判断"] || row["AI评级"]),
    };
  });
}

function scheduleApplyFilters() {
  window.clearTimeout(filterTimer);
  filterTimer = window.setTimeout(() => applyFilters(), 120);
}

function countBy(items, key) {
  return items.reduce((acc, item) => {
    const value = item[key] || "未知";
    acc[value] = (acc[value] || 0) + 1;
    return acc;
  }, {});
}

function fillSelect(id, values, labelFn = (value) => value) {
  const select = document.getElementById(id);
  if (!select) return;
  select.innerHTML = "";
  const all = document.createElement("option");
  all.value = "";
  all.textContent = "全部";
  select.appendChild(all);
  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = labelFn(value);
    select.appendChild(option);
  });
}

function prepareV2Rows(payload) {
  const items = Array.isArray(payload) ? payload : [payload];
  const rows = items.map((item) => {
    const data = item.data || {};
    const risk = item.risk || {};
    const quality = item.quality || {};
    const trend = item.trend || {};
    const valuation = item.valuation || {};
    const valuationResult = valuation.result || {};
    const routing = item.routing || {};
    const pool = item.pool || {};
    const evidence = item.evidence || {};
    const status = risk.status === "pass" ? "通过" : risk.status === "watch" || risk.status === "turnaround" ? "警惕" : risk.status === "special_analysis" ? "需专项分析" : risk.status === "exclude" ? "排除" : "数据不足";
    return {
      股票: item.symbol || "",
      市场: item.market || "",
      名称: item.company?.name || item.name || "",
      行业模型: routing.route || "",
      "数据年数": data.history_years ?? "",
      "数据质量": data.confidence || "未知",
      结果: status,
      分数: risk.score ?? "",
      "规则质量评级": quality.grade || "数据不足",
      "规则质量分": quality.score ?? "",
      原因: (risk.fatal_flags || []).join("；"),
      v2风险状态: risk.status || "",
      v2当前趋势: trend.state || "",
      v2估值状态: valuationResult.status || valuation.state || "indeterminate",
      v2估值置信度: valuationResult.valuation_confidence || valuation.confidence || "D",
      v2策略池: pool.pool || routing.route || "none",
      v2池资格: pool.eligible === true ? "是" : "否",
      "v2年报as-of": data.annual_data_as_of || "",
      "v2季度as-of": data.quarterly_data_as_of || "",
      "v2价格as-of": data.price_as_of || "",
      v2证据状态: evidence.status || (evidence.ai ? "validated" : "not_requested"),
      "质量理由": `覆盖通过=${quality.minimum_coverage_passed ? "是" : "否"}；缺失组件=${(quality.missing_components || []).join("、") || "无"}`,
      "综合观察": JSON.stringify({ valuation: valuationResult, pool, blocking_issues: data.blocking_issues || [] }, null, 2),
    };
  });
  return prepareRows(rows);
}

function prepareV2SummaryRows(items) {
  const rows = items.map((item) => {
    const status = item.risk_status === "pass" ? "通过" : item.risk_status === "watch" || item.risk_status === "turnaround" ? "警惕" : item.risk_status === "special_analysis" ? "需专项分析" : item.risk_status === "exclude" ? "排除" : "数据不足";
    return {
      股票: item.symbol || "",
      市场: item.market || "",
      名称: item.name || "",
      行业模型: item.route || "",
      "数据年数": item.history_years || "",
      "数据质量": item.data_confidence || "未知",
      结果: status,
      分数: item.risk_score ?? "",
      "规则质量评级": item.quality_grade || "not_available",
      "规则质量分": item.quality_score ?? "",
      原因: item.blocking_issues || "",
      v2风险状态: item.risk_status || "",
      v2当前趋势: item.trend_state || "",
      v2估值状态: item.valuation_status || "indeterminate",
      v2估值置信度: item.valuation_confidence || "D",
      v2策略池: item.pool || "none",
      v2池资格: item.pool_eligible === "True" ? "是" : "否",
      "v2年报as-of": item.annual_data_as_of || "",
      "v2季度as-of": item.quarterly_data_as_of || "",
      "v2价格as-of": item.price_as_of || "",
      v2证据状态: item.evidence_status || "not_requested",
      v2质量置信度: item.quality_confidence || "D",
      v2可评分权重: item.quality_scored_weight || "",
      v2排名资格: item.ranking_eligible === "True" ? "是" : "否",
      v2池内排名: item.rank_within_pool || "",
      "质量理由": `质量置信度=${item.quality_confidence || "D"}；可评分权重=${item.quality_scored_weight || "-"}`,
      "综合观察": [item.blocking_issues, item.route_blockers, item.pool_blockers].filter(Boolean).join("；") || "无阻断项",
      "数据版本": "investment_screen_v2_rules_no_ai",
      "AI评测状态": "未启用（规则版）",
    };
  });
  return prepareRows(rows);
}

function fillDatasetSelect() {
  const select = document.getElementById("datasetSelect");
  if (!select) return;
  select.innerHTML = DATASETS.map(
    (dataset, index) => `<option value="${index}">${escapeHtml(dataset.label)}</option>`
  ).join("");
}

function unique(key) {
  return [...new Set(rows.map((row) => row[key]).filter(Boolean))].sort();
}

function renderSummary() {
  const total = rows.length;
  const visible = filteredRows.length;
  const high = rows.filter((row) => row["数据质量"] === "High").length;
  const insufficient = rows.filter((row) => row["结果"] === "数据不足").length;
  const pass = rows.filter((row) => row["结果"] === "通过").length;
  const aiReviewed = rows.filter((row) => row._aiReviewed).length;
  const cards = [
    ["总股票数", total],
    ["当前可见", visible],
    ["High 数据质量", high],
    ["数据不足", insufficient],
    ["通过", pass],
    ["AI 复核", aiReviewed],
  ];
  document.getElementById("summaryCards").innerHTML = cards
    .map(
      ([label, value]) =>
        `<div class="card"><div class="label">${label}</div><div class="value">${value}</div></div>`
    )
    .join("");
}

function barColor(label) {
  if (label === "通过" || label === "High") return "var(--ok)";
  if (label === "警惕" || label === "需关注" || label === "Medium") return "var(--warn)";
  if (label === "排除") return "var(--danger)";
  return "var(--accent-2)";
}

function renderBars(id, counts) {
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...entries.map((entry) => entry[1]));
  document.getElementById(id).innerHTML = entries
    .slice(0, 10)
    .map(([label, count]) => {
      const width = Math.max(2, (count / max) * 100);
      return `<div class="bar-row">
        <span>${label}</span>
        <div class="bar-track"><div class="bar-fill" style="width:${width}%;background:${barColor(label)}"></div></div>
        <strong>${count}</strong>
      </div>`;
    })
    .join("");
}

function renderCharts() {
  renderBars("resultBars", countBy(filteredRows, "展示结果"));
  renderBars("qualityBars", countBy(filteredRows, "数据质量"));
  renderBars("industryBars", countBy(filteredRows, "行业模型"));
}

function pillClass(result) {
  if (result === "通过") return "pass";
  if (result === "警惕") return "warn";
  if (result === "排除") return "exclude";
  if (result === "数据不足") return "insufficient";
  if (result === "优质候选") return "pass";
  if (result === "可跟踪") return "track";
  if (result === "谨慎观察") return "warn";
  return "special";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderColumnHeader(column) {
  const help = columnHelp[column];
  if (!help) return escapeHtml(column);
  return `${escapeHtml(column)}<button class="help-button" type="button" data-help-key="${escapeHtml(column)}" aria-label="${escapeHtml(column)}评分说明">?</button>`;
}

function openHelp(key) {
  const title = key || "说明";
  const body = columnHelp[key] || "";
  const existing = document.getElementById("helpOverlay");
  if (existing) existing.remove();
  document.body.insertAdjacentHTML(
    "beforeend",
    `<div id="helpOverlay" class="help-overlay">
      <div class="help-popover" role="dialog" aria-modal="true" aria-labelledby="helpTitle">
        <div class="help-head">
          <h3 id="helpTitle">${escapeHtml(title)}</h3>
          <button class="help-close" type="button" aria-label="关闭">关闭</button>
        </div>
        <p>${escapeHtml(body)}</p>
      </div>
    </div>`
  );
  document.querySelector(".help-close")?.addEventListener("click", closeHelp);
  document.getElementById("helpOverlay")?.addEventListener("click", (event) => {
    if (event.target.id === "helpOverlay") closeHelp();
  });
}

function closeHelp() {
  document.getElementById("helpOverlay")?.remove();
}

function valueOf(row, key) {
  const value = row[key];
  return value && value !== "-" ? value : "";
}

function tableColumns() {
  const available = new Set(rows.flatMap((row) => Object.keys(row)));
  const detailless = baseColumns.filter((column) => column !== "详情" && available.has(column));
  const extras = optionalColumns.filter((column) => available.has(column));
  return [...detailless, ...extras, "详情"];
}

function renderBadge(value) {
  if (!value) return "-";
  return `<span class="pill ${pillClass(value)}">${escapeHtml(resultDisplayLabel(value))}</span>`;
}

function detailAction(label, action, value) {
  return `<button class="detail-action" type="button" data-action="${escapeHtml(action)}" data-value="${escapeHtml(value || "")}">${escapeHtml(label)}</button>`;
}

function resetFilterInputs() {
  document.getElementById("searchInput").value = "";
  document.getElementById("marketFilter").value = "";
  document.getElementById("resultFilter").value = "";
  document.getElementById("qualityFilter").value = "";
  document.getElementById("industryFilter").value = "";
  const ruleQualityFilter = document.getElementById("ruleQualityFilter");
  if (ruleQualityFilter) ruleQualityFilter.value = "";
  const aiRatingFilter = document.getElementById("aiRatingFilter");
  if (aiRatingFilter) aiRatingFilter.value = "";
  const disagreementFilter = document.getElementById("disagreementFilter");
  if (disagreementFilter) disagreementFilter.value = "";
  document.getElementById("minScore").value = 0;
  const aiOnlyFilter = document.getElementById("aiOnlyFilter");
  if (aiOnlyFilter) aiOnlyFilter.checked = false;
  currentPage = 1;
  activeTrait = null;
  renderTraitStatus();
}

function setSelectValue(id, value) {
  const select = document.getElementById(id);
  if (!select || !value) return;
  select.value = value;
}

function renderTraitStatus() {
  const status = document.getElementById("traitStatus");
  const text = document.getElementById("traitStatusText");
  if (!status || !text) return;
  if (!activeTrait) {
    status.hidden = true;
    text.textContent = "";
    return;
  }
  status.hidden = false;
  text.textContent = `特质检索：${traitFilters[activeTrait]?.label || activeTrait}`;
}

function resetFilterOptions() {
  fillSelect("marketFilter", unique("市场"));
  fillSelect("resultFilter", unique("结果"), resultDisplayLabel);
  fillSelect("qualityFilter", unique("数据质量"));
  fillSelect("industryFilter", unique("行业模型"));
  fillSelect("ruleQualityFilter", unique("规则质量评级"));
  fillSelect("aiRatingFilter", [...new Set([...unique("AI评级"), ...unique("AI判断")])].sort());
  fillSelect("disagreementFilter", unique("规则AI分歧"));
}

async function loadDataset(datasetIndex = 0) {
  const dataset = DATASETS[datasetIndex] || DATASETS[0];
  const response = await fetch(dataset.url);
  if (!response.ok) {
    throw new Error(`无法读取结果表：${dataset.url}`);
  }
  const raw = await response.text();
  rows = dataset.format === "v2" ? prepareV2Rows(JSON.parse(raw)) : dataset.format === "v2_summary" ? prepareV2SummaryRows(parseCsv(raw)) : prepareRows(parseCsv(raw));
  filteredRows = rows;
  currentPage = 1;
  sortState = dataset.defaultSort || (rows.some((row) => row["综合优质分"])
    ? { key: "综合优质分", direction: "desc" }
    : { key: "分数", direction: "asc" });
  resetFilterInputs();
  resetFilterOptions();
  applyFilters();
  const download = document.getElementById("downloadCsv");
  if (download) download.href = dataset.url;
  const subtitle = document.getElementById("subtitle");
  if (subtitle) subtitle.textContent = `当前结果表：${dataset.label}`;
  if (dataset.reportUrl) await loadReport(dataset.reportUrl, dataset.reportFormat);
}

function applyDetailSearch(action, value) {
  if (action === "stock") {
    resetFilterInputs();
    document.getElementById("searchInput").value = value;
  } else if (action === "market") {
    setSelectValue("marketFilter", value);
  } else if (action === "industry") {
    setSelectValue("industryFilter", value);
  } else if (action === "result") {
    setSelectValue("resultFilter", value);
  } else if (action === "ruleQuality") {
    setSelectValue("ruleQualityFilter", value);
  } else if (action === "aiRating") {
    setSelectValue("aiRatingFilter", value);
  } else if (action === "disagreement") {
    setSelectValue("disagreementFilter", value);
  } else if (action === "trait") {
    activeTrait = value;
    renderTraitStatus();
  }
  currentPage = 1;
  applyFilters();
  closeDetail();
  document.getElementById("resultsTable")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function sortRows(items) {
  const { key, direction } = sortState;
  const factor = direction === "asc" ? 1 : -1;
  return [...items].sort((a, b) => {
    const av = asNumber(a[key]);
    const bv = asNumber(b[key]);
    if (!Number.isNaN(av) && !Number.isNaN(bv)) return (av - bv) * factor;
    return String(a[key] || "").localeCompare(String(b[key] || ""), "zh-Hans") * factor;
  });
}

function renderTable() {
  const table = document.getElementById("resultsTable");
  const activeColumns = tableColumns();
  table.querySelector("colgroup")?.remove();
  table.insertAdjacentHTML(
    "afterbegin",
    `<colgroup>${activeColumns
      .map((column) => `<col style="width:${columnWidths[column] || "100px"}" />`)
      .join("")}</colgroup>`
  );
  table.querySelector("thead").innerHTML = `<tr>${activeColumns
    .map((column) => `<th data-key="${escapeHtml(column)}">${renderColumnHeader(column)}</th>`)
    .join("")}</tr>`;
  const sortedRows = sortRows(filteredRows);
  const totalPages = Math.max(1, Math.ceil(sortedRows.length / pageSize));
  currentPage = Math.min(Math.max(1, currentPage), totalPages);
  const start = (currentPage - 1) * pageSize;
  const displayRows = sortedRows.slice(start, start + pageSize);
  detailRows = displayRows;
  table.querySelector("tbody").innerHTML = displayRows
    .map((row, index) => {
      return `<tr>${activeColumns
        .map((column) => {
          if (column === "详情") {
            return `<td><button class="detail-button" type="button" data-index="${index}">详情</button></td>`;
          }
          const value = row[column] || "-";
          if (["结果", "规则质量评级", "AI评级", "AI判断", "规则AI分歧"].includes(column)) {
            return `<td><span class="pill ${pillClass(value)}">${escapeHtml(resultDisplayLabel(value))}</span></td>`;
          }
          return `<td>${escapeHtml(value)}</td>`;
        })
        .join("")}</tr>`;
    })
    .join("");
  const from = filteredRows.length ? start + 1 : 0;
  const to = Math.min(start + displayRows.length, filteredRows.length);
  document.getElementById("visibleCount").textContent = `筛选后 ${filteredRows.length}`;
  document.getElementById("tableRange").textContent = `显示 ${from}-${to} / ${filteredRows.length}`;
  document.getElementById("renderHint").textContent =
    filteredRows.length > pageSize ? "已启用分页渲染，详情信息点击按钮查看" : "";
  document.getElementById("pageStatus").textContent = `${currentPage} / ${totalPages}`;
  document.getElementById("prevPage").disabled = currentPage <= 1;
  document.getElementById("nextPage").disabled = currentPage >= totalPages;
  table.querySelectorAll("th").forEach((th) => {
    th.addEventListener("click", (event) => {
      if (event.target.closest(".help-button")) return;
      const key = th.dataset.key;
      sortState = {
        key,
        direction: sortState.key === key && sortState.direction === "asc" ? "desc" : "asc",
      };
      currentPage = 1;
      renderTable();
    });
  });
  table.querySelectorAll(".help-button").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      openHelp(button.dataset.helpKey);
    });
  });
  table.querySelectorAll(".detail-button").forEach((button) => {
    button.addEventListener("click", () => openDetail(Number(button.dataset.index)));
  });
}

function detailItem(label, value) {
  return `<div class="detail-item"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value || "-")}</strong></div>`;
}

function detailText(label, value) {
  if (!value) return "";
  return `<div class="detail-text"><h4>${escapeHtml(label)}</h4><p>${escapeHtml(value)}</p></div>`;
}

function openDetail(index) {
  const row = detailRows[index];
  if (!row) return;
  const aiRating = valueOf(row, "AI评级") || valueOf(row, "AI判断");
  const aiReason = valueOf(row, "AI理由") || valueOf(row, "AI原因");
  const aiRisk = valueOf(row, "AI风险") || valueOf(row, "AI风险点");
  const industry = valueOf(row, "行业模型") || valueOf(row, "行业");
  const content = document.getElementById("detailContent");
  content.innerHTML = `
    <div class="detail-title">
      <div>
        <h2>${escapeHtml(row["股票"] || "-")} ${escapeHtml(row["名称"] || "")}</h2>
        <p>${escapeHtml(row["市场"] || "-")} · ${escapeHtml(row["行业模型"] || row["行业"] || "-")}</p>
      </div>
      <div class="detail-badges">
        ${renderBadge(row["结果"])}
        ${renderBadge(row["规则质量评级"])}
        ${renderBadge(aiRating)}
      </div>
    </div>

    <section class="detail-section">
      <h3>检索这个股票或特质</h3>
      <div class="detail-actions">
        ${detailAction("只看这只股票", "stock", row["股票"])}
        ${detailAction("同市场", "market", row["市场"])}
        ${detailAction("同行业模型", "industry", industry)}
        ${detailAction("同排雷结果", "result", row["结果"])}
        ${detailAction("同规则质量", "ruleQuality", row["规则质量评级"])}
        ${detailAction("同AI评级", "aiRating", aiRating)}
        ${detailAction("同分歧状态", "disagreement", row["规则AI分歧"])}
        ${detailAction("高ROE", "trait", "highRoe")}
        ${detailAction("低负债", "trait", "lowDebt")}
        ${detailAction("高负债", "trait", "highDebt")}
        ${detailAction("规则+AI双优质", "trait", "ruleAiQuality")}
      </div>
    </section>

    <section class="detail-section">
      <h3>核心指标</h3>
      <div class="detail-grid">
        ${detailItem("PE", row["PE"])}
        ${detailItem("PB", row["PB"])}
        ${detailItem("10年ROE", row["10年ROE"])}
        ${detailItem("ROE波动", row["ROE波动"])}
        ${detailItem("5年平均FCF", row["5年平均FCF"])}
        ${detailItem("资产负债率", row["资产负债率"])}
        ${detailItem("数据年数", row["数据年数"])}
        ${detailItem("历史可信度", row["历史可信度"])}
        ${detailItem("数据质量", row["数据质量"])}
      </div>
      ${detailText("数据可信度说明", historyConfidenceNote(row))}
    </section>

    ${
      valueOf(row, "综合优质分")
        ? `<section class="detail-section">
            <h3>优质池排序</h3>
            <div class="detail-grid">
              ${detailItem("综合优质分", row["综合优质分"])}
              ${detailItem("优质池等级", row["优质池等级"])}
              ${detailItem("行业相对质量分", row["行业相对质量分"])}
              ${detailItem("资本效率分", row["资本效率分"])}
              ${detailItem("行业因子模型", row["行业因子模型"])}
              ${detailItem("入选来源", row["入选来源"])}
              ${detailItem("风险扣分", row["风险扣分"])}
            </div>
            ${detailText("排序理由", valueOf(row, "优质排序理由"))}
            ${detailText("行业相对理由", valueOf(row, "行业相对理由"))}
            ${detailText("资本效率理由", valueOf(row, "资本效率理由"))}
          </section>`
        : ""
    }

    <section class="detail-section">
      <h3>投资筛选 v2 主事实</h3>
      <div class="detail-grid">
        ${detailItem("风险状态", row["v2风险状态"])}
        ${detailItem("当前趋势", row["v2当前趋势"])}
        ${detailItem("估值状态", row["v2估值状态"])}
        ${detailItem("估值置信度", row["v2估值置信度"])}
        ${detailItem("策略池", row["v2策略池"])}
        ${detailItem("池资格", row["v2池资格"])}
        ${detailItem("证据状态", row["v2证据状态"])}
        ${detailItem("质量置信度", row["v2质量置信度"])}
        ${detailItem("可评分权重", row["v2可评分权重"])}
        ${detailItem("排名资格", row["v2排名资格"])}
        ${detailItem("池内排名", row["v2池内排名"])}
        ${detailItem("年度 as-of", row["v2年报as-of"])}
        ${detailItem("季度 as-of", row["v2季度as-of"])}
        ${detailItem("价格 as-of", row["v2价格as-of"])}
      </div>
      ${detailText("v2估值/池阻断", valueOf(row, "综合观察"))}
    </section>

    <section class="detail-section">
      <h3>规则排雷</h3>
      <div class="detail-grid">
        ${detailItem("结果", resultDisplayLabel(row["结果"]))}
        ${detailItem("规则原始状态", row["结果"])}
        ${detailItem("分数", row["分数"])}
        ${detailItem("杠杆风险", row["杠杆风险"])}
      </div>
      ${detailText("排雷原因", valueOf(row, "原因"))}
    </section>

    <section class="detail-section">
      <h3>规则质量</h3>
      <div class="detail-grid">
        ${detailItem("评级", row["规则质量评级"])}
        ${detailItem("质量分", row["规则质量分"])}
      </div>
      ${detailText("质量理由", valueOf(row, "质量理由"))}
    </section>

    <section class="detail-section">
      <h3>AI优质度</h3>
      <div class="detail-grid">
        ${detailItem("AI评测状态", row["AI评测状态"] || (aiRating ? "已评测" : "未评测"))}
        ${detailItem("AI评级", aiRating)}
        ${detailItem("AI置信度", row["AI置信度"])}
        ${detailItem("AI模型", row["AI模型"] || row["AI复核模型"])}
      </div>
      ${detailText("AI理由", aiReason)}
      ${detailText("AI风险", aiRisk)}
      ${detailText("AI关注点", valueOf(row, "AI关注点"))}
      ${detailText("AI护城河等级", valueOf(row, "AI护城河等级"))}
      ${detailText("AI护城河类型", valueOf(row, "AI护城河类型"))}
      ${detailText("AI护城河证据", valueOf(row, "AI护城河证据"))}
      ${detailText("AI护城河反证", valueOf(row, "AI护城河反证"))}
      ${detailText("AI证据等级", valueOf(row, "AI证据等级"))}
      ${detailText("AI定价权判断", valueOf(row, "AI定价权判断"))}
      ${detailText("AI客户粘性判断", valueOf(row, "AI客户粘性判断"))}
      ${detailText("AI竞争强度判断", valueOf(row, "AI竞争强度判断"))}
      ${detailText("AI资本效率判断", valueOf(row, "AI资本效率判断"))}
      ${detailText("AI管理层资本配置", valueOf(row, "AI管理层资本配置"))}
      ${detailText("AI领导人与文化证据", valueOf(row, "AI领导人与文化证据"))}
      ${detailText("AI管理层文化观察", valueOf(row, "AI管理层文化观察"))}
      ${detailText("AI外部验证需求", valueOf(row, "AI外部验证需求"))}
      ${detailText("AI护城河方法来源", valueOf(row, "AI护城河方法来源"))}
    </section>

    <section class="detail-section">
      <h3>综合观察</h3>
      <div class="detail-grid">
        ${detailItem("规则AI分歧", row["规则AI分歧"])}
      </div>
      ${detailText("说明", valueOf(row, "综合观察"))}
    </section>
  `;
  content.querySelectorAll(".detail-action").forEach((button) => {
    button.addEventListener("click", () => {
      applyDetailSearch(button.dataset.action, button.dataset.value);
    });
  });
  document.body.classList.add("drawer-open");
}

function closeDetail() {
  document.body.classList.remove("drawer-open");
}

function applyFilters() {
  const search = document.getElementById("searchInput").value.trim().toLowerCase();
  const market = document.getElementById("marketFilter").value;
  const result = document.getElementById("resultFilter").value;
  const quality = document.getElementById("qualityFilter").value;
  const industry = document.getElementById("industryFilter").value;
  const ruleQuality = document.getElementById("ruleQualityFilter")?.value || "";
  const aiRating = document.getElementById("aiRatingFilter")?.value || "";
  const disagreement = document.getElementById("disagreementFilter")?.value || "";
  const minScore = Number(document.getElementById("minScore").value || 0);
  const aiOnly = document.getElementById("aiOnlyFilter")?.checked || false;

  filteredRows = rows.filter((row) => {
    return (
      (!search || row._searchText.includes(search)) &&
      (!market || row["市场"] === market) &&
      (!result || row["结果"] === result) &&
      (!quality || row["数据质量"] === quality) &&
      (!industry || row["行业模型"] === industry) &&
      (!ruleQuality || row["规则质量评级"] === ruleQuality) &&
      (!aiRating || row["AI评级"] === aiRating || row["AI判断"] === aiRating) &&
      (!disagreement || row["规则AI分歧"] === disagreement) &&
      (!activeTrait || traitFilters[activeTrait]?.match(row)) &&
      (!aiOnly || row._aiReviewed) &&
      row._score >= minScore
    );
  });

  renderSummary();
  renderCharts();
  renderTable();
}

function renderReport(text) {
  document.getElementById("reportStatus").textContent = "已加载";
  const patterns = [
    ["US 耗时", /US_SECONDS=([\d.]+)/],
    ["CN 耗时", /CN_SECONDS=([\d.]+)/],
    ["标准化年度记录", /Normalized annual rows: (\d+)/],
    ["US 缺失比例", /US missing field ratio: .*?\((.*?)\)/],
    ["CN 缺失比例", /CN missing field ratio: .*?\((.*?)\)/],
    ["US ok", /US symbol status:[\s\S]*?ok: (\d+).*?\((.*?)\)/],
    ["US skipped", /US symbol status:[\s\S]*?skipped: (\d+).*?\((.*?)\)/],
    ["CN ok", /CN symbol status:[\s\S]*?ok: (\d+).*?\((.*?)\)/],
  ];
  document.getElementById("reportGrid").innerHTML = patterns
    .map(([label, regex]) => {
      const match = text.match(regex);
      const value = match ? (match[2] ? `${match[1]} (${match[2]})` : match[1]) : "-";
      return `<div class="report-item"><strong>${label}</strong><span>${value}</span></div>`;
    })
    .join("");
}

function renderV2Manifest(manifest) {
  document.getElementById("reportStatus").textContent = "已加载 · 无AI评测";
  const risk = manifest.counts?.risk_status || {};
  const trend = manifest.counts?.trend_state || {};
  const values = [
    ["股票总数", manifest.stock_count],
    ["风险通过", risk.pass],
    ["需要关注", risk.watch],
    ["专项分析", risk.special_analysis],
    ["数据不足", risk.data_insufficient],
    ["趋势不可用", trend.not_available],
    ["正式排名", manifest.ranked_count],
    ["AI/API调用", manifest.network_calls],
  ];
  document.getElementById("reportGrid").innerHTML = values
    .map(([label, value]) => `<div class="report-item"><strong>${label}</strong><span>${value ?? "-"}</span></div>`)
    .join("");
}

async function loadReport(reportUrl, format = "legacy") {
  const status = document.getElementById("reportStatus");
  if (status) status.textContent = "加载中";
  try {
    const response = await fetch(reportUrl);
    if (!response.ok) throw new Error(reportUrl);
    const text = await response.text();
    if (format === "v2_manifest") renderV2Manifest(JSON.parse(text));
    else renderReport(text);
  } catch (error) {
    if (status) status.textContent = "未加载";
    document.getElementById("reportGrid").innerHTML = "";
  }
}

function attachEvents() {
  document.getElementById("searchInput")?.addEventListener("input", () => {
    currentPage = 1;
    scheduleApplyFilters();
  });
  ["marketFilter", "resultFilter", "qualityFilter", "industryFilter", "ruleQualityFilter", "aiRatingFilter", "disagreementFilter", "minScore", "aiOnlyFilter"].forEach(
    (id) =>
      document.getElementById(id)?.addEventListener("input", () => {
        currentPage = 1;
        applyFilters();
      })
  );
  document.getElementById("resetFilters").addEventListener("click", () => {
    resetFilterInputs();
    applyFilters();
  });
  document.getElementById("pageSizeSelect")?.addEventListener("change", (event) => {
    pageSize = Number(event.target.value || 100);
    currentPage = 1;
    renderTable();
  });
  document.getElementById("prevPage")?.addEventListener("click", () => {
    currentPage -= 1;
    renderTable();
    document.getElementById("tableWrap")?.scrollTo({ top: 0 });
  });
  document.getElementById("nextPage")?.addEventListener("click", () => {
    currentPage += 1;
    renderTable();
    document.getElementById("tableWrap")?.scrollTo({ top: 0 });
  });
  document.getElementById("clearTraitFilter")?.addEventListener("click", () => {
    activeTrait = null;
    currentPage = 1;
    renderTraitStatus();
    applyFilters();
  });
  document.getElementById("datasetSelect")?.addEventListener("change", (event) => {
    loadDataset(Number(event.target.value)).catch((error) => {
      document.body.innerHTML = `<main class="panel"><h1>加载失败</h1><p>${escapeHtml(error.message)}</p></main>`;
    });
  });
  document.getElementById("detailClose")?.addEventListener("click", closeDetail);
  document.getElementById("detailOverlay")?.addEventListener("click", closeDetail);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeHelp();
    if (event.key === "Escape") closeDetail();
  });
}

async function init() {
  fillDatasetSelect();
  attachEvents();
  await loadDataset(0);
}

init().catch((error) => {
  const fileHelp =
    location.protocol === "file:"
      ? `<p>你现在是直接打开本地 HTML 文件。浏览器会阻止页面读取本地 CSV，所以需要用本地静态服务或 GitHub Pages 打开。</p>
         <pre><code>cd /d D:\\四步排雷\\public
python -m http.server 8766</code></pre>
         <p>然后打开 <a href="http://127.0.0.1:8766/">http://127.0.0.1:8766/</a></p>`
      : "";
  document.body.innerHTML = `<main class="panel load-error"><h1>加载失败</h1><p>${escapeHtml(error.message)}</p>${fileHelp}</main>`;
});

// B4 accepts a pre-validated pure view model only.  This page never derives a
// valuation from CSV fields and therefore cannot turn a low price/PE/PB into a
// quality upgrade or a fabricated recommendation.
function renderB4Watchlist(view) {
  const status = document.getElementById("b4WatchlistStatus");
  const grid = document.getElementById("b4WatchlistGrid");
  if (!status || !grid) return;
  if (!view || typeof view !== "object") {
    status.textContent = "未载入经验证的 B4 view model";
    grid.innerHTML = "";
    return;
  }
  const valuation = view.valuation || {};
  const freshness = view.freshness || {};
  const state = view.watchlist_state || {};
  const evidence = view.evidence || {};
  const quality = view.enterprise_quality || {};
  const calibration = view.calibration || {};
  const calibrationData = calibration.calibration || {};
  const calibrationCoverage = calibrationData.holdout_rates?.coverage;
  const cards = [
    ["四象限", view.quadrant?.label || "不可分类"],
    ["企业质量", `${quality.band || "unknown"} / ${quality.grade || "-"}`],
    ["证据置信度", evidence.evidence_confidence || "unknown"],
    ["估值状态", valuation.status || "not_valuable"],
    ["情景", Array.isArray(valuation.scenario_results) ? `${valuation.scenario_results.length} 个` : "0 个"],
    ["价格新鲜度", freshness.price || "unknown"],
    ["证据新鲜度", freshness.evidence || "unknown"],
    ["观察清单", state.status || "new"],
    ["A4 校准", calibration.status || "not_available"],
    ["A4 覆盖率", typeof calibrationCoverage === "number" ? `${(calibrationCoverage * 100).toFixed(1)}%` : "不可用"],
  ];
  const blockers = Array.isArray(valuation.blocking_reasons) ? valuation.blocking_reasons : [];
  const calibrationBlockers = Array.isArray(calibration.blocking_reasons) ? calibration.blocking_reasons : [];
  status.textContent = blockers.length
    ? `不可估值：${blockers.map((item) => item.code || item.message).join("；")}`
    : calibrationBlockers.length
      ? `A4 校准不可用：${calibrationBlockers.map((item) => item.code || item.message).join("；")}`
      : "已载入经验证的 B4 view model";
  grid.innerHTML = cards
    .map(([label, value]) => `<div class="b4-watchlist-card"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`)
    .join("");
}

window.renderB4Watchlist = renderB4Watchlist;
renderB4Watchlist(window.B4_WATCHLIST_VIEW);
