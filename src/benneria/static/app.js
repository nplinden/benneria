const $ = (s) => document.querySelector(s);
const out = $("#out");
let lastResults = [];

// esc, chip, entryLink and renderEntry (the dictionary entry card) are in entry-card.js,
// shared with the statistics page.

// ---------- filters ----------
// These run in the browser on the returned entries; they never change the request.
// Choices persist across searches until the page is reloaded; everything is shown by default.
const langChoice = new Map();  // "Hebrew" / "Aramaic" -> shown?
const posChoice = new Map();   // Lexical Index part-of-speech code -> shown?

const entryLang = (e) => e.lang === "arc" ? "Aramaic" : "Hebrew";
const entryPos = (e) => e.pos || "";
const langShown = (l) => langChoice.get(l) ?? true;
const posShown = (p) => posChoice.get(p) ?? true;
const entryShown = (e) => langShown(entryLang(e)) && posShown(entryPos(e));

function countBy(items, key) {
  const m = new Map();
  items.forEach(x => m.set(key(x), (m.get(key(x)) || 0) + 1));
  return m;
}

function renderFilters() {
  const has = lastResults.length > 0;
  $("#filtersEmpty").hidden = has;
  $("#langRow").hidden = !has;
  $("#langFilters").innerHTML = [...countBy(lastResults, entryLang)].map(([l, n]) =>
    `<label><input type="checkbox" data-lang="${esc(l)}" ${langShown(l) ? "checked" : ""}> ${esc(l)} (${n})</label>`
  ).join("");
  const parts = countBy(lastResults, entryPos);
  $("#posRow").hidden = !parts.size;
  $("#posFilters").innerHTML = [...parts].sort((a, b) => b[1] - a[1]).map(([p, n]) =>
    `<label title="${esc(p || "no part of speech given")}"><input type="checkbox" data-pos="${esc(p)}" ${posShown(p) ? "checked" : ""}> ${esc(p ? posName(p) : "No part of speech")} (${n})</label>`
  ).join("");
}
$("#filterGroup").addEventListener("change", (ev) => {
  const d = ev.target.dataset;
  if (d.lang !== undefined) langChoice.set(d.lang, ev.target.checked);
  else if (d.pos !== undefined) posChoice.set(d.pos, ev.target.checked);
  else return;
  renderFilters();
  renderResults();
});

function renderResults() {
  const shown = lastResults.filter(entryShown);
  // Note above the results when filters hide some of them.
  const hidden = lastResults.length - shown.length;
  $("#optsCount").hidden = !hidden;
  $("#optsCount").textContent = hidden ? `Showing ${shown.length} of ${lastResults.length} entries; ${hidden} hidden by the filters in Options.` : "";
  out.innerHTML = shown.map(renderEntry).join("") ||
    `<div class="status">No entries match the result filters. Adjust them in Options (the gear next to the search button).</div>`;
}

// ---------- search ----------
const SEARCH_OPTIONS = ["lookup_ref", "always_consonants", "always_split", "never_split", "strip_prefixes"];
const OPEN_KEYS = ["id", "bdb", "strong"];  // cross-references: /api/entry?id=, ?bdb=, ?strong=

async function lookup(word, push = true) {
  word = word.trim();
  if (!word) return;
  $("#q").value = word;
  const params = new URLSearchParams({ word });
  for (const k of SEARCH_OPTIONS) {
    const v = document.getElementById(k).value.trim();
    if (v) params.set(k, v);
  }
  if (push) history.pushState({ word }, "", "?" + params.toString());
  await fetchResults("/api/lookup?" + params.toString(), `No dictionary entries found for
    <span class="he">${esc(word)}</span>. Try turning on “Ignore vowels” or “Look up each word”.`);
}

// Opens entries named by a cross-reference (an entry id, BDB id or Strong's number).
async function openEntry(kind, value, push = true) {
  const params = new URLSearchParams({ [kind]: value });
  if (push) history.pushState({ [kind]: value }, "", "?" + params.toString());
  await fetchResults("/api/entry?" + params.toString(), "No entry found for this reference.");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function fetchResults(url, emptyMessage) {
  document.body.classList.remove("home");
  out.innerHTML = `<div class="status">Searching…</div>`;
  lastResults = [];
  renderFilters();
  $("#optsCount").hidden = true;
  try {
    const r = await fetch(url);
    const data = await r.json();
    if (!r.ok || data.error) throw new Error(data.error || `HTTP ${r.status}`);
    lastResults = data.results || [];
    if (!lastResults.length) {
      out.innerHTML = `<div class="status">${emptyMessage}</div>`;
      return true;
    }
    renderFilters();
    renderResults();
    return true;
  } catch (err) {
    out.innerHTML = `<div class="status error">${esc(err.message)}</div>`;
    return false;
  }
}

$("#f").addEventListener("submit", (ev) => { ev.preventDefault(); lookup($("#q").value); });
$("#apiGroup").addEventListener("change", () => { if ($("#q").value.trim()) lookup($("#q").value); });
document.addEventListener("click", (ev) => {
  const a = ev.target.closest("[data-word]");
  if (a) { ev.preventDefault(); lookup(a.dataset.word); window.scrollTo({ top: 0, behavior: "smooth" }); return; }
  // Cross-references inside entries: related entries, BDB and Strong's links.
  const x = ev.target.closest("[data-entry], [data-bdb], [data-strong]");
  if (x) {
    ev.preventDefault();
    const d = x.dataset;
    if (d.entry) openEntry("id", d.entry);
    else if (d.bdb) openEntry("bdb", d.bdb);
    else openEntry("strong", d.strong);
  }
});
function route(push) {
  const p = new URLSearchParams(location.search);
  const kind = OPEN_KEYS.find(k => p.get(k));
  if (kind) openEntry(kind, p.get(kind), push);
  else if (p.get("word")) lookup(p.get("word"), push);
  else showWelcome();
}
window.addEventListener("popstate", () => route(false));

function showWelcome() {
  document.body.classList.add("home");
  lastResults = [];
  $("#q").value = "";
  renderFilters();
  $("#optsCount").hidden = true;
  out.innerHTML = "";
}

// ---------- options dialog ----------
const optsDialog = $("#opts");
$("#optsBtn").addEventListener("click", () => optsDialog.showModal());
$("#optsClose").addEventListener("click", () => optsDialog.close());
// A click on the backdrop (outside the dialog's box) closes it; Escape closes it natively.
optsDialog.addEventListener("click", (ev) => { if (ev.target === optsDialog) optsDialog.close(); });
// The context field is outside the search form, so Enter there re-runs the search itself.
$("#lookup_ref").addEventListener("keydown", (ev) => {
  if (ev.key === "Enter" && $("#q").value.trim()) { ev.preventDefault(); lookup($("#q").value); }
});


// ---------- init ----------
const init = new URLSearchParams(location.search);
for (const k of SEARCH_OPTIONS)
  if (init.get(k)) document.getElementById(k).value = init.get(k);
route(false);
