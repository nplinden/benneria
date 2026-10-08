const $ = (s) => document.querySelector(s);
const out = $("#out");
let lastResults = [];
const lexChoice = new Map();  // lexicon -> shown?, set when the user toggles a filter

// ---------- helpers ----------
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c =>
  ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const safeDecode = (s) => { try { return decodeURIComponent(s); } catch { return s; } };
const safeUrl = (u) => /^https?:\/\//i.test(String(u ?? "")) ? u : "";

// Sefaria definitions contain HTML. Keep a safe subset of it and route links.
const OK_TAGS = new Set(["A","B","I","EM","STRONG","SPAN","SUP","SUB","BR","SMALL","BIG","U","P","DIV"]);
function sanitize(html) {
  const doc = new DOMParser().parseFromString(`<div>${html ?? ""}</div>`, "text/html");
  const root = doc.body.firstChild;
  // Pass 1: drop dangerous elements, unwrap any other non-whitelisted tag.
  root.querySelectorAll("script,style,iframe,object,embed,noscript,template").forEach(el => el.remove());
  let bad;
  while ((bad = [...root.querySelectorAll("*")].find(el => !OK_TAGS.has(el.tagName)))) {
    bad.replaceWith(...bad.childNodes);
  }
  // Pass 2: strip attributes and route links (each element visited once).
  const walk = (node) => {
    [...node.children].forEach(el => {
      const href = el.tagName === "A" ? el.getAttribute("href") : null;
      [...el.attributes].forEach(a => { if (a.name !== "dir") el.removeAttribute(a.name); });
      if (href !== null) {
        const m = href.match(/^\/?words?\/([^?#]+)/) || href.match(/[?&]lookup=([^&#]+)/);
        if (m) { el.setAttribute("data-word", safeDecode(m[1])); el.setAttribute("href", "#"); }
        else if (/^\//.test(href)) { el.setAttribute("href", "https://www.sefaria.org" + href); el.setAttribute("target","_blank"); el.setAttribute("rel","noopener"); }
        else if (/^https?:/i.test(href)) { el.setAttribute("href", href); el.setAttribute("target","_blank"); el.setAttribute("rel","noopener"); }
      }
      walk(el);
    });
  };
  walk(doc.body.firstChild);
  return doc.body.firstChild.innerHTML;
}

function chip(label, value) {
  if (value === undefined || value === null || value === "" || value === false) return "";
  if (Array.isArray(value)) { if (!value.length) return ""; value = value.join(", "); }
  if (value === true) return `<span class="chip">${esc(label)}</span>`;
  return `<span class="chip">${label ? `<b>${esc(label)}</b> ` : ""}${sanitize(String(value))}</span>`;
}

function grammarText(g) {
  if (!g) return "";
  const parts = [];
  if (g.verbal_stem) parts.push(g.verbal_stem);
  if (g.binyan_form) parts.push(Array.isArray(g.binyan_form) ? g.binyan_form.join(", ") : g.binyan_form);
  if (g.morphology) parts.push(g.morphology);
  if (g.language_code) parts.push(g.language_code);
  return parts.join(" · ");
}

function renderSenses(senses) {
  if (!Array.isArray(senses) || !senses.length) return "";
  const items = senses.map(s => {
    if (typeof s === "string") return `<li>${sanitize(s)}</li>`;
    let h = "";
    const num = s.number || s.num;
    if (s.pre_num) h += `<span class="note">${sanitize(s.pre_num)}</span> `;
    if (num) h += `<span class="num">${esc(num)}</span>`;
    const g = grammarText(s.grammar) || s.form || "";
    if (g) h += `<span class="stem">${esc(g)}</span>`;
    if (s.morphology) h += `<span class="stem">${esc(s.morphology)}</span>`;
    if (s.definition) h += sanitize(s.definition);
    if (s.alternative) h += ` <span class="note">(alt. ${sanitize(s.alternative)})</span>`;
    if (s.plural_form) h += ` <span class="note">pl. ${sanitize(Array.isArray(s.plural_form) ? s.plural_form.join(", ") : s.plural_form)}</span>`;
    if (s.occurrences || s.occurences) h += ` <span class="note">(${esc(s.occurrences || s.occurences)}×)</span>`;
    if (s.all_cited) h += ` <span class="note" title="All occurrences cited">†</span>`;
    if (s.note) h += `<div class="note">${sanitize(s.note)}</div>`;
    if (s.notes) h += `<div class="note">${sanitize(s.notes)}</div>`;
    if (s.senses) h += renderSenses(s.senses);
    return `<li>${h}</li>`;
  }).join("");
  return `<ol class="senses">${items}</ol>`;
}

function altHeadwords(a) {
  if (!a) return "";
  if (!Array.isArray(a)) a = [a];
  return a.map(x => typeof x === "object" ? (x.word || "") + (x.occurrences || x.occurences ? ` (${x.occurrences || x.occurences}×)` : "") : x)
          .filter(Boolean).join(", ");
}

function wordLink(w) { return `<a data-word="${esc(w)}" href="#" class="he">${esc(w)}</a>`; }

function renderEntry(e) {
  const c = e.content || {};
  const lex = e.parent_lexicon || "Dictionary";
  let hwExtra = "";
  if (e.headword_suffix) hwExtra += ` ${esc(e.headword_suffix)}`;
  if (e.ordinal) hwExtra += ` <small>${esc(e.ordinal)}</small>`;
  if (e.root) hwExtra += ` <small>root</small>`;
  if (e.peculiar) hwExtra += ` <small title="Peculiar to Biblical Aramaic">‡</small>`;
  if (e.all_cited) hwExtra += ` <small title="All occurrences cited">†</small>`;

  const meta = [
    chip("", entryLex(e) === MORPH_LEX && entryMorph(e) ? morphName(entryMorph(e)) : c.morphology || e.morphology),
    chip("", langName(e.language_code)),
    chip("Strong's", e.strong_number || e.strong_numbers),
    chip("TWOT", e.TWOT),
    chip("GK", e.GK),
    chip("Occurrences", e.occurrences),
    chip("Plural", e.plural_form),
    chip("Also", altHeadwords(e.alt_headwords)),
    chip("Ref.", e.language_reference),
  ].join("");

  let body = renderSenses(c.senses);
  if (!body && typeof c === "string") body = `<div>${sanitize(c)}</div>`;
  if (e.notes) body += `<div class="note">${sanitize(e.notes)}</div>`;
  if (e.derivatives) body += `<div class="note"><b>Derivatives:</b> ${sanitize(e.derivatives)}</div>`;
  if (e.quotes && (Array.isArray(e.quotes) ? e.quotes.length : true))
    body += `<div class="note"><b>Quotes:</b> ${sanitize(Array.isArray(e.quotes) ? e.quotes.join("; ") : e.quotes)}</div>`;

  let refs = "";
  if (Array.isArray(e.refs) && e.refs.length) {
    refs = `<div class="refs">Sources: ` + e.refs.map(r =>
      `<a href="https://www.sefaria.org/${encodeURIComponent(r.replace(/ /g, "_"))}" target="_blank" rel="noopener">${esc(r)}</a>`
    ).join(" · ") + `</div>`;
  }

  let nav = "";
  if (e.prev_hw || e.next_hw) {
    nav = `<div class="nav"><span>${e.prev_hw ? "← " + wordLink(e.prev_hw) : ""}</span>
           <span>${e.next_hw ? wordLink(e.next_hw) + " →" : ""}</span></div>`;
  }

  const d = e.parent_lexicon_details || {};
  let attrib = "";
  if (d.source || d.attribution) {
    const srcUrl = safeUrl(d.source_url), attUrl = safeUrl(d.attribution_url);
    const src = d.source ? (srcUrl ? `<a href="${esc(srcUrl)}" target="_blank" rel="noopener">${esc(d.source)}</a>` : esc(d.source)) : "";
    const att = d.attribution ? (attUrl ? `<a href="${esc(attUrl)}" target="_blank" rel="noopener">${esc(d.attribution)}</a>` : esc(d.attribution)) : "";
    attrib = `<div class="attrib">${[src, att].filter(Boolean).join(" — ")}</div>`;
  }

  return `<article class="entry">
    <div class="entry-head">
      <div class="hw" dir="rtl">${esc(e.headword)}${hwExtra}</div>
      <div class="lex">${esc(lex)}</div>
    </div>
    ${meta ? `<div class="meta">${meta}</div>` : ""}
    ${body || `<div class="note">No definition text in this entry.</div>`}
    ${refs}${nav}${attrib}
  </article>`;
}

// Local backend entry. Its BDB and Strong's HTML is generated by scripts/build_data.py from
// escaped XML text and a fixed set of tags, so it is inserted as is.
function renderLocalEntry(e) {
  const s = e.strongs || {};
  const meta = [
    chip("", s.pos ? morphName(s.pos) : ""),
    chip("", langName(e.lang)),
    chip("Strong's", e.strong && /^\d/.test(e.strong) ? e.strong + (e.aug || "") : ""),
    chip("TWOT", e.twot),
    chip("BDB p.", e.bdb && e.bdb.page),
    chip("Occurrences", e.count || ""),
  ].join("");

  const forms = e.matches.length ? `<div class="forms"><b>Found as</b> ${e.matches.map(m =>
    `<span class="form${m.in_ref ? " in-ref" : ""}"><span class="he" dir="rtl">${esc(m.form)}</span>
      <code title="morphhb parse">${esc(m.morph)}</code>${m.variant ? ` <i>${esc(m.variant)}</i>` : ""}
      ×${m.count} <small>${esc(m.refs.join(", "))}${m.count > m.refs.length ? "…" : ""}</small></span>`
  ).join("")}</div>` : "";

  let body = "";
  if (s.meaning_html) body += `<div>${s.meaning_html}</div>`;
  if (s.usage_html) body += `<div class="note"><b>Usage:</b> ${s.usage_html}</div>`;
  if (s.source_html) body += `<div class="note"><b>Source:</b> ${s.source_html}</div>`;
  if (e.bdb) body += `<details class="bdb"><summary>Brown-Driver-Briggs</summary>${e.bdb.html}</details>`;

  const related = e.related.length ? `<div class="refs">${e.related[0].relation === "origin" ? "From" : "Derivatives"}: ${
    e.related.map(r => `${wordLink(r.headword)}${r.gloss ? ` <small>${esc(r.gloss)}</small>` : ""}`).join(" · ")}</div>` : "";
  const nav = `<div class="nav"><span>${e.prev ? "← " + wordLink(e.prev.headword) : ""}</span>
    <span>${e.next ? wordLink(e.next.headword) + " →" : ""}</span></div>`;

  return `<article class="entry">
    <div class="entry-head">
      <div class="hw" dir="rtl">${esc(e.headword)}${e.bdb && e.bdb.homonym ? ` <small>${esc(e.bdb.homonym)}</small>` : ""}</div>
      <div class="lex">${esc(e.gloss || "")}</div>
    </div>
    ${meta ? `<div class="meta">${meta}</div>` : ""}
    ${forms}${body || `<div class="note">No definition text in this entry.</div>`}
    ${related}${nav}
  </article>`;
}

// ---------- filters ----------
// These run in the browser on the returned entries; they never change the request.
// Choices persist across searches until the page is reloaded.
// Local results are grouped by language (Hebrew/Aramaic) instead of by dictionary.
const DEFAULT_LEXICONS = new Set(["BDB Augmented Strong", "Hebrew", "Aramaic"]);
const MORPH_LEX = "BDB Augmented Strong";  // the only lexicon with Strong's-style morph codes
const morphChoice = new Map();  // morph code -> shown?, set when the user toggles a filter

const entryLex = (e) => e.local ? (e.lang === "arc" ? "Aramaic" : "Hebrew") : e.parent_lexicon || "Dictionary";
const entryMorph = (e) => String((e.content && e.content.morphology) || e.morphology || "").trim();
const lexShown = (l) => lexChoice.has(l) ? lexChoice.get(l) : DEFAULT_LEXICONS.has(l);
const morphShown = (m) => morphChoice.get(m) ?? true;
const entryShown = (e) => lexShown(entryLex(e)) && (entryLex(e) !== MORPH_LEX || morphShown(entryMorph(e)));

function countBy(items, key) {
  const m = new Map();
  items.forEach(x => m.set(key(x), (m.get(key(x)) || 0) + 1));
  return m;
}

function renderFilters() {
  const has = lastResults.length > 0;
  $("#filtersEmpty").hidden = has;
  $("#lexRow").hidden = !has;
  $("#filters").innerHTML = [...countBy(lastResults, entryLex)].map(([l, n]) =>
    `<label><input type="checkbox" data-lex="${esc(l)}" ${lexShown(l) ? "checked" : ""}> ${esc(l)} (${n})</label>`
  ).join("");

  const morphs = countBy(lastResults.filter(e => entryLex(e) === MORPH_LEX), entryMorph);
  $("#morphRow").hidden = !morphs.size;
  $("#morphRow").classList.toggle("inactive", !lexShown(MORPH_LEX));
  $("#morphFilters").innerHTML = [...morphs].sort((a, b) => b[1] - a[1]).map(([m, n]) =>
    `<label title="${esc(m || "no morphology given")}"><input type="checkbox" data-morph="${esc(m)}" ${morphShown(m) ? "checked" : ""}> ${esc(morphName(m))} (${n})</label>`
  ).join("");
}
$("#filterGroup").addEventListener("change", (ev) => {
  const d = ev.target.dataset;
  if (d.lex !== undefined) lexChoice.set(d.lex, ev.target.checked);
  else if (d.morph !== undefined) morphChoice.set(d.morph, ev.target.checked);
  else return;
  renderFilters();
  renderResults();
});

function renderResults() {
  const shown = lastResults.filter(entryShown);
  $("#optsCount").textContent = lastResults.length ? ` · showing ${shown.length} of ${lastResults.length} entries` : "";
  out.innerHTML = shown.map(e => e.local ? renderLocalEntry(e) : renderEntry(e)).join("") ||
    `<div class="status">No entries match the result filters. Adjust them under Options.</div>`;
}

// ---------- history ----------
function getHistory() { try { return JSON.parse(localStorage.getItem("sefaria-dict-history") || "[]"); } catch { return []; } }
function pushHistory(w) {
  const h = [w, ...getHistory().filter(x => x !== w)].slice(0, 12);
  try { localStorage.setItem("sefaria-dict-history", JSON.stringify(h)); } catch {}
  renderHistory();
}
function renderHistory() {
  const h = getHistory();
  $("#history").innerHTML = h.length ? "Recent: " + h.map(w => `<a data-word="${esc(w)}">${esc(w)}</a>`).join("") : "";
}

// ---------- search ----------
async function lookup(word, push = true) {
  word = word.trim();
  if (!word) return;
  $("#q").value = word;
  const params = new URLSearchParams({ word });
  for (const k of ["lookup_ref", "always_consonants", "always_split", "never_split"]) {
    const v = document.getElementById(k).value.trim();
    if (v) params.set(k, v);
  }
  if (push) history.pushState({ word }, "", "?" + params.toString());
  out.innerHTML = `<div class="status">Searching…</div>`;
  lastResults = [];
  renderFilters();
  $("#optsCount").textContent = "";
  try {
    const r = await fetch("/api/lookup?" + params.toString());
    const data = await r.json();
    if (!r.ok || data.error) throw new Error(data.error || `HTTP ${r.status}`);
    // The Sefaria backend returns a list of entries; the local one an object with its results.
    lastResults = Array.isArray(data) ? data
      : data.backend === "local" ? data.results.map(e => ({ ...e, local: true })) : [];
    pushHistory(word);
    if (!lastResults.length) {
      out.innerHTML = `<div class="status">No dictionary entries found for <span class="he">${esc(word)}</span>.
        Try turning on “Ignore vowels” or “Substring matches”.</div>`;
      return;
    }
    renderFilters();
    renderResults();
  } catch (err) {
    out.innerHTML = `<div class="status error">${esc(err.message)}</div>`;
  }
}

$("#f").addEventListener("submit", (ev) => { ev.preventDefault(); lookup($("#q").value); });
$("#apiGroup").addEventListener("change", () => { if ($("#q").value.trim()) lookup($("#q").value); });
document.addEventListener("click", (ev) => {
  const a = ev.target.closest("[data-word]");
  if (a) { ev.preventDefault(); lookup(a.dataset.word); window.scrollTo({ top: 0, behavior: "smooth" }); }
});
window.addEventListener("popstate", () => {
  const p = new URLSearchParams(location.search);
  if (p.get("word")) lookup(p.get("word"), false);
  else showWelcome();
});

function showWelcome() {
  lastResults = [];
  $("#q").value = "";
  renderFilters();
  $("#optsCount").textContent = "";
  out.innerHTML = `<div class="status">Enter a word to search Sefaria's dictionaries.<br>
    Try ${["תורה","שלום","ראה","אמר"].map(w => `<a data-word="${w}" href="#" class="he">${w}</a>`).join(" · ")}</div>`;
}

// ---------- Hebrew keyboard ----------
const letters = "אבגדהוזחטיכךלמםנןסעפףצץקרשת".split("").concat(["־", "⌫", "␣"]);
$("#kb").innerHTML = letters.map(l => `<button type="button" data-k="${l}">${l}</button>`).join("");
$("#kb").addEventListener("click", (ev) => {
  const k = ev.target.dataset.k; if (!k) return;
  const q = $("#q");
  if (k === "⌫") q.value = q.value.slice(0, -1);
  else if (k === "␣") q.value += " ";
  else q.value += k;
  q.focus();
});
$("#kbBtn").addEventListener("click", () => $("#kb").classList.toggle("show"));

// ---------- init ----------
renderHistory();
const init = new URLSearchParams(location.search);
for (const k of ["lookup_ref", "always_consonants", "always_split", "never_split"])
  if (init.get(k)) document.getElementById(k).value = init.get(k);
if (init.get("word")) lookup(init.get("word"), false);
else showWelcome();
