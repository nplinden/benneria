"""
Sefaria Dictionary — a small, standalone web app.

Uses only the Python standard library. It serves a small web UI and proxies
lookups to the Sefaria Lexicon API (GET https://www.sefaria.org/api/words/{word}).

Run:
    uv run sefaria                           # http://127.0.0.1:8000
    uv run sefaria --port 9000 --host 0.0.0.0 --open
"""

import argparse
import json
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SEFARIA_BASE = "https://www.sefaria.org/api/words/"
ALLOWED_PARAMS = ("lookup_ref", "never_split", "always_split", "always_consonants")
TIMEOUT = 20
CACHE = {}          # simple in-memory cache: url -> (status, body)
CACHE_MAX = 500
CACHE_LOCK = threading.Lock()  # requests are served on multiple threads


def fetch_words(word, params):
    query = {k: v for k, v in params.items() if k in ALLOWED_PARAMS and v != ""}
    url = SEFARIA_BASE + urllib.parse.quote(word, safe="")
    if query:
        url += "?" + urllib.parse.urlencode(query)
    with CACHE_LOCK:
        cached = CACHE.get(url)
    if cached:
        return cached
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "sefaria-dictionary-webapp/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read()
            status = resp.status
    except urllib.error.HTTPError as e:
        body = json.dumps({"error": f"Sefaria returned HTTP {e.code}"}).encode()
        status = 502
    except Exception as e:  # network errors, timeouts
        body = json.dumps({"error": f"Could not reach Sefaria: {e}"}).encode()
        status = 502
    if status == 200:
        with CACHE_LOCK:
            if url not in CACHE and len(CACHE) >= CACHE_MAX:
                CACHE.pop(next(iter(CACHE)))
            CACHE[url] = (status, body)
    return status, body


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sefaria Dictionary</title>
<style>
  :root {
    --bg: #f7f5f0; --card: #ffffff; --ink: #1f2430; --muted: #6b7080;
    --line: #e4e0d6; --accent: #18345d; --accent-2: #b8862b; --chip: #eef1f6;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #14161b; --card: #1d2027; --ink: #e8e6e1; --muted: #9aa0ad;
      --line: #2e323b; --accent: #8fb3e8; --accent-2: #e0b25a; --chip: #262a33;
    }
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--ink);
         font: 16px/1.55 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
  header { padding: 28px 16px 8px; text-align: center; }
  header h1 { margin: 0; font-family: Georgia, "Times New Roman", serif;
              font-weight: 500; letter-spacing: .5px; color: var(--accent); }
  header p { margin: 4px 0 0; color: var(--muted); font-size: 14px; }
  main { max-width: 860px; margin: 0 auto; padding: 0 16px 60px; }
  form { background: var(--card); border: 1px solid var(--line); border-radius: 14px;
         padding: 16px; margin: 18px 0; position: sticky; top: 8px; z-index: 5;
         box-shadow: 0 4px 20px rgba(0,0,0,.05); }
  .row { display: flex; gap: 8px; }
  input[type=text] { flex: 1; min-width: 0; font-size: 20px; padding: 10px 14px;
         border: 1px solid var(--line); border-radius: 10px; background: var(--bg);
         color: var(--ink); font-family: "SBL Hebrew", "Ezra SIL", "Taamey Frank CLM",
         "David", "Times New Roman", serif; }
  input[type=text]:focus { outline: 2px solid var(--accent); outline-offset: 1px; }
  button { font: inherit; padding: 10px 18px; border-radius: 10px; border: 0;
           background: var(--accent); color: var(--card); cursor: pointer; font-weight: 600; }
  button.ghost { background: transparent; color: var(--muted); border: 1px solid var(--line);
                 font-weight: 400; padding: 6px 10px; font-size: 13px; }
  details.opts { margin-top: 10px; font-size: 14px; color: var(--muted); }
  details.opts summary { cursor: pointer; }
  .opts-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
               gap: 10px; margin-top: 10px; }
  .opts-grid label { display: flex; flex-direction: column; gap: 4px; }
  .opts-grid select, .opts-grid input { font: inherit; padding: 6px 8px; border-radius: 8px;
               border: 1px solid var(--line); background: var(--bg); color: var(--ink); }
  .keyboard { display: none; flex-wrap: wrap; gap: 4px; margin-top: 10px; direction: rtl; }
  .keyboard.show { display: flex; }
  .keyboard button { background: var(--chip); color: var(--ink); padding: 6px 0; width: 38px;
                     font-family: serif; font-size: 18px; font-weight: 400; }
  .toolbar { display: flex; justify-content: space-between; align-items: center;
             flex-wrap: wrap; gap: 8px; margin-top: 10px; }
  .filters { display: flex; flex-wrap: wrap; gap: 6px; }
  .filters label { background: var(--chip); border-radius: 999px; padding: 3px 10px;
                   font-size: 13px; cursor: pointer; user-select: none; }
  .status { color: var(--muted); text-align: center; padding: 24px; }
  .error { color: #c0392b; }
  .entry { background: var(--card); border: 1px solid var(--line); border-radius: 14px;
           padding: 18px 20px; margin: 14px 0; }
  .entry-head { display: flex; justify-content: space-between; align-items: baseline;
                gap: 12px; flex-wrap: wrap; border-bottom: 1px solid var(--line);
                padding-bottom: 10px; margin-bottom: 10px; }
  .hw { font-family: "SBL Hebrew", "Ezra SIL", "Taamey Frank CLM", "David", serif;
        font-size: 32px; line-height: 1.2; direction: rtl; }
  .hw small { font-size: 16px; color: var(--muted); margin-inline-start: 8px; }
  .lex { font-size: 13px; font-weight: 600; color: var(--accent-2); text-transform: uppercase;
         letter-spacing: .6px; }
  .meta { display: flex; flex-wrap: wrap; gap: 6px; margin: 6px 0 10px; }
  .chip { background: var(--chip); border-radius: 6px; padding: 2px 8px; font-size: 13px; }
  .chip b { color: var(--muted); font-weight: 500; }
  ol.senses { margin: 6px 0; padding-inline-start: 22px; }
  ol.senses ol.senses { margin: 4px 0; }
  ol.senses li { margin: 3px 0; }
  .stem { font-weight: 600; color: var(--accent); margin-inline-end: 6px; font-style: italic; }
  .num { font-weight: 700; margin-inline-end: 4px; }
  .note { color: var(--muted); font-size: 14px; margin-top: 8px; }
  .nav { display: flex; justify-content: space-between; gap: 8px; margin-top: 12px;
         font-size: 14px; }
  .nav a, .refs a, .entry a { color: var(--accent); text-decoration: none; cursor: pointer; }
  .nav a:hover, .entry a:hover { text-decoration: underline; }
  .refs { font-size: 13px; color: var(--muted); margin-top: 8px; }
  .attrib { font-size: 12px; color: var(--muted); margin-top: 10px; }
  .history { font-size: 13px; color: var(--muted); margin-top: 8px; display: flex;
             flex-wrap: wrap; gap: 6px; align-items: center; }
  .history a { background: var(--chip); padding: 2px 8px; border-radius: 6px; cursor: pointer;
               font-family: serif; font-size: 15px; color: var(--ink); }
  [dir=rtl], .he { font-family: "SBL Hebrew", "Ezra SIL", "David", serif; }
  footer { text-align: center; color: var(--muted); font-size: 12px; padding: 20px; }
</style>
</head>
<body>
<header>
  <h1>Sefaria Dictionary</h1>
  <p>Jastrow · BDB · Strong's · Klein, via the Sefaria Lexicon API</p>
</header>
<main>
  <form id="f" autocomplete="off">
    <div class="row">
      <input id="q" type="text" dir="auto" placeholder="Type a Hebrew or Aramaic word… e.g. תורה" autofocus>
      <button type="submit">Look up</button>
    </div>
    <div class="toolbar">
      <div class="filters" id="filters"></div>
      <button type="button" class="ghost" id="kbBtn">א Keyboard</button>
    </div>
    <div class="keyboard" id="kb"></div>
    <details class="opts">
      <summary>Search options</summary>
      <div class="opts-grid">
        <label>Context reference (lookup_ref)
          <input id="lookup_ref" type="text" placeholder="e.g. Leviticus 19.3" dir="ltr" style="font-size:14px">
        </label>
        <label>Ignore vowels (always_consonants)
          <select id="always_consonants"><option value="">Default</option><option value="1">Yes</option><option value="0">No</option></select>
        </label>
        <label>Substring matches (always_split)
          <select id="always_split"><option value="">Default</option><option value="1">Yes</option><option value="0">No</option></select>
        </label>
        <label>Exact input only (never_split)
          <select id="never_split"><option value="">Default</option><option value="1">Yes</option><option value="0">No</option></select>
        </label>
      </div>
    </details>
    <div class="history" id="history"></div>
  </form>
  <div id="out"></div>
</main>
<footer>Data from <a href="https://www.sefaria.org" target="_blank" rel="noopener">Sefaria</a>. Each dictionary keeps its own license and attribution.</footer>

<script>
const $ = (s) => document.querySelector(s);
const out = $("#out");
let lastResults = [];
const hidden = new Set();

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
  return `<span class="chip"><b>${esc(label)}</b> ${sanitize(String(value))}</span>`;
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
    chip("Translit.", e.transliteration),
    chip("Pron.", e.pronunciation),
    chip("Morph.", c.morphology || e.morphology),
    chip("Lang.", e.language_code),
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

// ---------- filters ----------
function renderFilters() {
  const lexes = [...new Set(lastResults.map(e => e.parent_lexicon || "Dictionary"))];
  $("#filters").innerHTML = lexes.length > 1 ? lexes.map(l => {
    const n = lastResults.filter(e => (e.parent_lexicon || "Dictionary") === l).length;
    return `<label><input type="checkbox" data-lex="${esc(l)}" ${hidden.has(l) ? "" : "checked"}> ${esc(l)} (${n})</label>`;
  }).join("") : "";
}
$("#filters").addEventListener("change", (ev) => {
  const l = ev.target.dataset.lex; if (!l) return;
  ev.target.checked ? hidden.delete(l) : hidden.add(l);
  renderResults();
});

function renderResults() {
  const shown = lastResults.filter(e => !hidden.has(e.parent_lexicon || "Dictionary"));
  out.innerHTML = shown.map(renderEntry).join("") ||
    `<div class="status">All results are filtered out.</div>`;
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
  $("#filters").innerHTML = "";
  try {
    const r = await fetch("/api/lookup?" + params.toString());
    const data = await r.json();
    if (!r.ok || data.error) throw new Error(data.error || `HTTP ${r.status}`);
    lastResults = Array.isArray(data) ? data : [];
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
  $("#filters").innerHTML = "";
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
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "SefariaDictionary/1.0"

    def _send(self, status, body, ctype):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            return self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        if parsed.path == "/api/lookup":
            qs = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}
            word = qs.pop("word", "").strip()
            if not word:
                body = json.dumps({"error": "Missing 'word' parameter"}).encode()
                return self._send(400, body, "application/json")
            status, body = fetch_words(word, qs)
            return self._send(status, body, "application/json; charset=utf-8")
        if parsed.path == "/favicon.ico":
            return self._send(204, b"", "image/x-icon")
        self._send(404, b"Not found", "text/plain")

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))


def main():
    ap = argparse.ArgumentParser(description="Standalone Sefaria dictionary web app")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--open", action="store_true", help="open the browser on start")
    args = ap.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{'localhost' if args.host in ('0.0.0.0', '127.0.0.1') else args.host}:{args.port}/"
    print(f"Sefaria Dictionary running at {url}  (Ctrl+C to stop)")
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
        server.server_close()


if __name__ == "__main__":
    main()
