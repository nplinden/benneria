const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c =>
  ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const PAGE_SIZE = 10;

let roots = [];       // every root: {root, total, <binyan>: count, ...} (from /api/stats/roots)
let binyanim = [];    // common binyanim, in display order
let tenses = [];      // the eight tenses, in chart-stacking order (from /api/stats/chart)

let sortKey = "total";
let sortDir = "desc";
let page = 0;
let filterText = "";           // the root filter box, a plain substring match
const selected = new Set();    // roots clicked in the table, restricting the chart
let anchorRoot = null;         // last root clicked, where a shift+click range starts from

// ---------- table ----------

function columns() {
  return ["root", "total", ...binyanim];
}

const COLUMN_LABELS = { root: "Root", total: "Total" };

function filteredSortedRoots() {
  const key = sortKey, dir = sortDir === "asc" ? 1 : -1;
  const filtered = filterText ? roots.filter(r => r.root.includes(filterText)) : roots;
  return [...filtered].sort((a, b) => {
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
  const all = filteredSortedRoots();
  const start = page * PAGE_SIZE;
  const pageRows = all.slice(start, start + PAGE_SIZE);
  const rowsHtml = pageRows.map(r => `
    <tr class="${selected.has(r.root) ? "selected" : ""}" data-root="${esc(r.root)}">
      ${cols.map(c => c === "root"
        ? `<td class="root-cell he" dir="rtl">${esc(r.root)}</td>`
        : `<td>${r[c]}</td>`).join("")}
    </tr>`);
  if (!rowsHtml.length) rowsHtml.push(`<tr><td colspan="${cols.length}" class="status">No roots match.</td></tr>`);
  // Padded to a full page of rows, so filtering down to fewer roots doesn't shrink the table
  // card (and, with it, the chart card stretched to match its height).
  while (rowsHtml.length < PAGE_SIZE) rowsHtml.push(`<tr class="filler-row"><td colspan="${cols.length}">&nbsp;</td></tr>`);
  $("#statsBody").innerHTML = rowsHtml.join("");
  renderPager(all.length);
}

let lastPageIndex = 0;

function renderPager(total) {
  lastPageIndex = Math.max(1, Math.ceil(total / PAGE_SIZE)) - 1;
  page = Math.min(page, lastPageIndex);
  $("#pageInfo").textContent = `Page ${page + 1} of ${lastPageIndex + 1} · ${total} roots`;
  $("#firstPage").disabled = page === 0;
  $("#prevPage").disabled = page === 0;
  $("#nextPage").disabled = page >= lastPageIndex;
  $("#lastPage").disabled = page >= lastPageIndex;
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

// Plain click: select just this row (replacing any other selection), or deselect it if it was
// the only one selected. Ctrl/Cmd+click adds it to the selection. Shift+click adds every row
// between the last-clicked row and this one, in the table's current sort order. With nothing
// selected yet, all three act like a plain click.
$("#statsBody").addEventListener("click", (ev) => {
  const row = ev.target.closest("[data-root]");
  if (!row) return;
  const root = row.dataset.root;

  if (selected.size && ev.shiftKey && anchorRoot && filteredSortedRoots().some(r => r.root === anchorRoot)) {
    const order = filteredSortedRoots().map(r => r.root);
    const [lo, hi] = [order.indexOf(anchorRoot), order.indexOf(root)].sort((a, b) => a - b);
    for (let i = lo; i <= hi; i++) selected.add(order[i]);
  } else if (selected.size && (ev.ctrlKey || ev.metaKey)) {
    selected.add(root);
  } else if (selected.size === 1 && selected.has(root)) {
    selected.clear();
  } else {
    selected.clear();
    selected.add(root);
  }
  anchorRoot = root;
  renderBody();
  refreshChart();
});

$("#firstPage").addEventListener("click", () => { page = 0; renderBody(); });
$("#prevPage").addEventListener("click", () => { page--; renderBody(); });
$("#nextPage").addEventListener("click", () => { page++; renderBody(); });
$("#lastPage").addEventListener("click", () => { page = lastPageIndex; renderBody(); });

$("#rootFilter").addEventListener("input", (ev) => {
  filterText = ev.target.value.trim();
  $("#clearFilter").hidden = !filterText;
  page = 0;
  renderBody();
});

$("#clearFilter").addEventListener("click", () => {
  $("#rootFilter").value = "";
  filterText = "";
  $("#clearFilter").hidden = true;
  page = 0;
  renderBody();
  $("#rootFilter").focus();
});

// ---------- chart ----------

async function refreshChart() {
  const params = new URLSearchParams();
  for (const root of selected) params.append("root", root);
  const r = await fetch("/api/stats/chart?" + params.toString());
  const data = await r.json();
  tenses = data.tenses;
  renderChart(data.data);
  $("#chartTitle").innerHTML = selected.size === 0 ? "Every root"
    : selected.size === 1
      ? `<a href="/lexicon?word=${encodeURIComponent([...selected][0])}" class="he">${esc([...selected][0])}</a>`
      : `${selected.size} roots`;
}

// Each binyan's own colour (matching this page's author's Anki palette; see stats.css).
const BINYAN_COLORS = {
  Paal: "var(--binyan-paal)", Piel: "var(--binyan-piel)", Hifil: "var(--binyan-hifil)",
  Hitpael: "var(--binyan-hitpael)", Hofal: "var(--binyan-hofal)", Pual: "var(--binyan-pual)",
  Nifal: "var(--binyan-nifal)",
};

function renderChart(rows) {
  const totals = rows.map(row => tenses.reduce((sum, t) => sum + row[t], 0));
  const max = Math.max(1, ...totals);
  $("#chartRows").innerHTML = rows.map((row, i) => {
    const tooltip = tenses.filter(t => row[t]).map(t => `${t}: ${row[t]}`).join("\n");
    return `
    <div class="chart-row">
      <span class="chart-row-label">${esc(row.binyan)}</span>
      <div class="chart-row-track"><div class="chart-bar" title="${esc(tooltip)}"
        style="width:${totals[i] / max * 100}%; background:${BINYAN_COLORS[row.binyan] || "var(--muted)"}"></div></div>
      <span class="chart-row-total">${totals[i]}</span>
    </div>`;
  }).join("");
}

// ---------- init ----------

(async () => {
  const data = await (await fetch("/api/stats/roots")).json();
  roots = data.roots;
  binyanim = data.binyanim;
  renderHead();
  renderBody();
  await refreshChart();
})();
