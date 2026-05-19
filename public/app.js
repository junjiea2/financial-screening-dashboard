const DATASETS = [
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

const columns = [
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

function valueOf(row, key) {
  const value = row[key];
  return value && value !== "-" ? value : "";
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
  rows = prepareRows(parseCsv(await response.text()));
  filteredRows = rows;
  currentPage = 1;
  sortState = { key: "分数", direction: "asc" };
  resetFilterInputs();
  resetFilterOptions();
  applyFilters();
  const download = document.getElementById("downloadCsv");
  if (download) download.href = dataset.url;
  const subtitle = document.getElementById("subtitle");
  if (subtitle) subtitle.textContent = `当前结果表：${dataset.label}`;
  await loadReport(dataset.reportUrl);
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
  table.querySelector("thead").innerHTML = `<tr>${columns
    .map((column) => `<th data-key="${column}">${column}</th>`)
    .join("")}</tr>`;
  const sortedRows = sortRows(filteredRows);
  const totalPages = Math.max(1, Math.ceil(sortedRows.length / pageSize));
  currentPage = Math.min(Math.max(1, currentPage), totalPages);
  const start = (currentPage - 1) * pageSize;
  const displayRows = sortedRows.slice(start, start + pageSize);
  detailRows = displayRows;
  table.querySelector("tbody").innerHTML = displayRows
    .map((row, index) => {
      return `<tr>${columns
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
    th.addEventListener("click", () => {
      const key = th.dataset.key;
      sortState = {
        key,
        direction: sortState.key === key && sortState.direction === "asc" ? "desc" : "asc",
      };
      currentPage = 1;
      renderTable();
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
        ${detailItem("AI评级", aiRating)}
        ${detailItem("AI置信度", row["AI置信度"])}
        ${detailItem("AI模型", row["AI模型"] || row["AI复核模型"])}
      </div>
      ${detailText("AI理由", aiReason)}
      ${detailText("AI风险", aiRisk)}
      ${detailText("AI关注点", valueOf(row, "AI关注点"))}
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

async function loadReport(reportUrl) {
  const status = document.getElementById("reportStatus");
  if (status) status.textContent = "加载中";
  try {
    const response = await fetch(reportUrl);
    if (!response.ok) throw new Error(reportUrl);
    renderReport(await response.text());
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
