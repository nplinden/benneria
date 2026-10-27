const $ = (s) => document.querySelector(s);
const PAGE_SIZE = 20;

let roots = [];       // every root: {root, total, <binyan>: count, ...} (from /api/stats/roots)
let binyanim = [];    // common binyanim, in display order
let tenses = [];      // the eight tenses, in chart-stacking order (from /api/stats/chart)

let sortKey = "total";
let sortDir = "desc";
let page = 0;
const extraCols = new Set();   // binyan columns shown beside Root/Total
const selected = new Set();    // roots clicked in the table, restricting the chart and definitions

// ---------- table ----------

function columns() {
  return ["root", "total", ...binyanim.filter(b => extraCols.has(b))];
}

const COLUMN_LABELS = { root: "Root", total: "Total" };

function sortedRoots() {
  const key = sortKey, dir = sortDir === "asc" ? 1 : -1;
  return [...roots].sort((a, b) => {
    if (key === "root") return dir * a.root.localeCompare(b.root);
    return dir * (a[key] - b[key]);
  });
}

function renderHead() {
  $("#statsHead").innerHTML = columns().map(key => {
    const sorted = key === sortKey;
    const arrow = sorted ? `<span class="arrow">${sortDir === "asc" ? "▲" : "▼"}</span>` : "";
    return `<th data-key="${key}" class="${sorted ? "sorted" : ""}">${COLUMN_LABELS[key] || key}${arrow}</th>`;
  }).join("");
}

function renderBody() {
  const cols = columns();
  const all = sortedRoots();
  const start = page * PAGE_SIZE;
  const pageRows = all.slice(start, start + PAGE_SIZE);
  $("#statsBody").innerHTML = pageRows.map(r => `
    <tr class="${selected.has(r.root) ? "selected" : ""}">
      ${cols.map(c => c === "root"
        ? `<td class="root-cell he" dir="rtl" data-root="${esc(r.root)}">${esc(r.root)}</td>`
        : `<td>${r[c]}</td>`).join("")}
    </tr>`).join("") || `<tr><td colspan="${cols.length}" class="status">No roots.</td></tr>`;
  renderPager(all.length);
}

function renderPager(total) {
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  page = Math.min(page, pages - 1);
  $("#pageInfo").textContent = `Page ${page + 1} of ${pages} · ${total} roots`;
  $("#prevPage").disabled = page === 0;
  $("#nextPage").disabled = page >= pages - 1;
}

$("#statsHead").addEventListener("click", (ev) => {
  const th = ev.target.closest("th");
  if (!th) return;
  const key = th.dataset.key;
  if (key === sortKey) sortDir = sortDir === "asc" ? "desc" : "asc";
  else { sortKey = key; sortDir = key === "root" ? "asc" : "desc"; }
  page = 0;
  renderHead();
  renderBody();
});

$("#statsBody").addEventListener("click", (ev) => {
  const cell = ev.target.closest("[data-root]");
  if (!cell) return;
  const root = cell.dataset.root;
  selected.has(root) ? selected.delete(root) : selected.add(root);
  renderBody();
  refreshChart();
  refreshDefinitions();
});

$("#prevPage").addEventListener("click", () => { page--; renderBody(); });
$("#nextPage").addEventListener("click", () => { page++; renderBody(); });

// ---------- binyan column toggles ----------

function renderBinyanToggles() {
  $("#binyanToggles").innerHTML = binyanim.map(b =>
    `<label><input type="checkbox" data-binyan="${esc(b)}" ${extraCols.has(b) ? "checked" : ""}> ${esc(b)}</label>`
  ).join("");
}

$("#binyanToggles").addEventListener("change", (ev) => {
  const b = ev.target.dataset.binyan;
  if (b === undefined) return;
  ev.target.checked ? extraCols.add(b) : extraCols.delete(b);
  if (!extraCols.has(sortKey) && sortKey !== "root" && sortKey !== "total") sortKey = "total";
  renderHead();
  renderBody();
});

// ---------- chart ----------

async function refreshChart() {
  const params = new URLSearchParams();
  for (const root of selected) params.append("root", root);
  const r = await fetch("/api/stats/chart?" + params.toString());
  const data = await r.json();
  tenses = data.tenses;
  renderChart(data.data);
  $("#chartTitle").textContent = selected.size ? [...selected].join(", ") : "Every root";
}

function renderChart(rows) {
  const totals = rows.map(row => tenses.reduce((sum, t) => sum + row[t], 0));
  const max = Math.max(1, ...totals);
  $("#chartRows").innerHTML = rows.map((row, i) => `
    <div class="chart-row">
      <span class="chart-row-label">${esc(row.binyan)}</span>
      <div class="chart-row-track"><div class="chart-bar" style="width:${totals[i] / max * 100}%">
        ${tenses.map((t, ti) => row[t] ? `<span class="chart-seg" style="flex:${row[t]} 1 0%; background: var(--tense-${ti})" title="${esc(t)}: ${row[t]}"></span>` : "").join("")}
      </div></div>
      <span class="chart-row-total">${totals[i]}</span>
    </div>`).join("");
  $("#chartLegend").innerHTML = tenses.map((t, ti) =>
    `<span><i class="swatch" style="background: var(--tense-${ti})"></i>${esc(t)}</span>`).join("");
}

// ---------- definitions ----------

async function refreshDefinitions() {
  const div = $("#definitions");
  if (!selected.size) { div.innerHTML = ""; return; }
  const sections = await Promise.all([...selected].sort().map(async (root) => {
    const r = await fetch("/api/entry?" + new URLSearchParams({ root }));
    const data = await r.json();
    const body = data.results.length ? data.results.map(renderEntry).join("")
      : `<p class="status">No definition found.</p>`;
    return `<h3 class="def-root-head">${esc(root)}</h3>${body}`;
  }));
  div.innerHTML = sections.join("");
}

// ---------- init ----------

(async () => {
  const data = await (await fetch("/api/stats/roots")).json();
  roots = data.roots;
  binyanim = data.binyanim;
  renderBinyanToggles();
  renderHead();
  renderBody();
  await refreshChart();
})();
