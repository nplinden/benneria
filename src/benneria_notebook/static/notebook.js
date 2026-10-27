const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c =>
  ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));

// ---------- state ----------
let toc = null;                 // /api/toc: parts → books → chapters, with created chapters
let current = null;             // the open notebook: /api/notebooks/<book>/<chapter>
const openBooks = new Set();    // books expanded in the sidebar

// The book-name language is a per-browser preference.
const NAMES_KEY = "benneria-notebook-names";
let names = (() => { try { return localStorage.getItem(NAMES_KEY) || "fr"; } catch { return "fr"; } })();
$("#names").value = names;

const bookName = (osis) => (BOOK_NAMES[osis] || {})[names] || osis;
const number = (n) => names === "he" ? hebrewNumeral(n) : String(n);
const reference = (osis, chapter, verse) =>
  `${bookName(osis)} ${number(chapter)}${verse ? ":" + number(verse) : ""}`;
const dir = () => names === "he" ? "rtl" : "ltr";

// ---------- sidebar ----------
function renderToc() {
  $("#toc").innerHTML = toc.parts.map(part => `
    <section class="toc-part">
      <h2 dir="${dir()}">${esc(PART_NAMES[part.id][names])}</h2>
      ${part.books.map(book => {
        const created = new Set(book.created);
        const open = openBooks.has(book.osis);
        const chapters = Array.from({ length: book.chapters }, (_, i) => i + 1).map(c => {
          const active = current && current.book === book.osis && current.chapter === c;
          return `<button type="button" class="chapter${created.has(c) ? " created" : ""}${active ? " active" : ""}"
            data-book="${book.osis}" data-chapter="${c}"
            title="${esc(reference(book.osis, c))}${created.has(c) ? "" : " (pas encore de carnet)"}">${number(c)}</button>`;
        }).join("");
        return `<div class="toc-book${open ? " open" : ""}">
          <button type="button" class="book" data-toggle="${book.osis}" dir="${dir()}" aria-expanded="${open}">
            <span>${esc(bookName(book.osis))}</span>${created.size ? `<small>${created.size}</small>` : ""}
          </button>
          ${open ? `<div class="chapters" dir="${dir()}">${chapters}</div>` : ""}
        </div>`;
      }).join("")}
    </section>`).join("");
}

$("#toc").addEventListener("click", (ev) => {
  const toggle = ev.target.closest("[data-toggle]");
  if (!toggle) return;
  const osis = toggle.dataset.toggle;
  openBooks.has(osis) ? openBooks.delete(osis) : openBooks.add(osis);
  renderToc();
});

// Double-click opens a chapter's notebook, creating it the first time.
$("#toc").addEventListener("dblclick", (ev) => {
  const button = ev.target.closest(".chapter");
  if (!button) return;
  openNotebook(button.dataset.book, Number(button.dataset.chapter));
});

// ---------- notebook view ----------
async function openNotebook(book, chapter, push = true) {
  await flushNotes();  // save what's being typed before leaving the chapter
  try {
    let r = await fetch(`/api/notebooks/${book}/${chapter}`);
    if (r.status === 404) {
      // Not created yet: create it now.
      r = await fetch(`/api/notebooks/${book}/${chapter}`, { method: "POST" });
    }
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
    current = data;
    openBooks.add(book);
    markCreated(book, chapter);
    if (push) history.pushState({ book, chapter }, "", `?c=${book}.${chapter}`);
    renderToc();
    renderNotebook();
  } catch (err) {
    $("#view").innerHTML = `<p class="status error">${esc(err.message)}</p>`;
  }
}

function markCreated(book, chapter) {
  for (const part of toc.parts)
    for (const b of part.books)
      if (b.osis === book && !b.created.includes(chapter)) b.created.push(chapter);
}

function renderNotebook() {
  if (!current) {
    $("#view").innerHTML = `<p class="status">Double-cliquez sur un chapitre pour ouvrir son carnet.</p>`;
    return;
  }
  const { book, chapter, verses } = current;
  document.title = `${reference(book, chapter)} · Benneria Notebook`;
  $("#view").innerHTML = `
    <div class="chapter-head">
      <h1 class="chapter-title" dir="${dir()}">${esc(reference(book, chapter))}</h1>
      <button type="button" class="delete-notebook" title="Supprimer ce carnet, ses notes et ses tableaux">Supprimer ce carnet</button>
    </div>
    ${verses.map(v => `
      <section class="admonition" id="v${v.verse}">
        <div class="admonition-head" dir="${dir()}"><span aria-hidden="true">✦</span> ${esc(reference(book, chapter, v.verse))}</div>
        <p class="verse-text he" dir="rtl" lang="he">${esc(v.text)}</p>
      </section>
      <div class="verb-table-box" data-verse="${v.verse}">${tableView(v)}</div>
      <div class="verse-note" data-verse="${v.verse}">${noteView(v)}<span class="save-status" aria-live="polite"></span></div>`).join("")}`;
  window.scrollTo({ top: 0 });
}

// ---------- notes between verses ----------
// Each verse is followed by a note, written in Markdown (markdown.js). Click it to edit; it is
// saved shortly after you stop typing and when you leave it (an empty note is removed).
const SAVE_DELAY = 800;  // ms after the last keystroke
// What's not saved yet, by "kind:book.chapter.verse" (kind: "notes" or "tables"):
// {kind, book, chapter, verse, body, timer, inFlight, again}. Keyed by chapter too, so a save still
// under way when you change chapter goes to the right place.
const saves = new Map();
const saveKey = (kind, book, chapter, verse) => `${kind}:${book}.${chapter}.${verse}`;

const verseOf = (n) => current.verses.find(v => v.verse === n);

function noteView(v) {
  const label = `Note après ${esc(reference(current.book, current.chapter, v.verse))}`;
  return v.note.trim()
    ? `<div class="note-view" tabindex="0" role="button" aria-label="${label}">${renderMarkdown(v.note)}</div>`
    : `<div class="note-view empty" tabindex="0" role="button" aria-label="${label}">Ajouter une note…</div>`;
}

function startEditing(box) {
  if (box.querySelector("textarea")) return;
  const verse = Number(box.dataset.verse);
  const { book, chapter } = current;
  const key = saveKey("notes", book, chapter, verse);
  const area = document.createElement("textarea");
  area.className = "note-edit";
  area.dir = "auto";
  area.placeholder = "Note en Markdown : *italique*, **gras**, - listes…";
  area.value = verseOf(verse).note;
  box.querySelector(".note-view").replaceWith(area);
  const fit = () => { area.style.height = "auto"; area.style.height = area.scrollHeight + 2 + "px"; };
  area.addEventListener("input", () => {
    fit();
    verseOf(verse).note = area.value;
    queueSave({ kind: "notes", book, chapter, verse }, { text: area.value });
  });
  area.addEventListener("keydown", (ev) => { if (ev.key === "Escape") area.blur(); });
  area.addEventListener("blur", () => {
    saveNow(key);
    if (area.isConnected) area.replaceWith(htmlToNode(noteView(verseOf(verse))));
  });
  fit();
  area.focus();
  area.setSelectionRange(area.value.length, area.value.length);
}

const htmlToNode = (html) => { const t = document.createElement("template"); t.innerHTML = html; return t.content.firstChild; };

// The save status next to a note or table, if its chapter is the one on screen.
function setStatus(s, text, kind = "") {
  if (!current || current.book !== s.book || current.chapter !== s.chapter) return;
  const box = s.kind === "notes" ? ".verse-note" : ".verb-table-box";
  const el = document.querySelector(`${box}[data-verse="${s.verse}"] .save-status`);
  if (el) { el.textContent = text; el.className = `save-status ${kind}`; }
}

// Schedule a save of a note ({text}) or a table ({rows}) after the typing pause.
function queueSave(where, payload, delay = SAVE_DELAY) {
  const key = saveKey(where.kind, where.book, where.chapter, where.verse);
  const s = saves.get(key) || { ...where };
  clearTimeout(s.timer);
  s.body = JSON.stringify(payload);
  s.timer = setTimeout(() => saveNow(key), delay);
  saves.set(key, s);
  setStatus(s, "Modifié…");
}

// Save now. A save never overtakes another: if one is under way, the newest version is saved right
// after it, and the returned promise covers both.
function saveNow(key) {
  const s = saves.get(key);
  if (!s) return Promise.resolve();
  clearTimeout(s.timer);
  if (s.inFlight) { s.again = true; return s.inFlight; }
  const body = s.body;
  setStatus(s, "Enregistrement…");
  s.inFlight = fetch(`/api/notebooks/${s.book}/${s.chapter}/${s.kind}/${s.verse}`, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body })
    .then(async r => {
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || `HTTP ${r.status}`);
      if (s.body === body && !s.again) { saves.delete(key); setStatus(s, "Enregistré", "saved"); }
    })
    .catch(err => setStatus(s, `Non enregistré : ${err.message}`, "error"))  // kept; retried on the next change
    .then(() => {
      s.inFlight = null;
      if (s.again) { s.again = false; return saveNow(key); }
    });
  return s.inFlight;
}

const flushNotes = () => Promise.all([...saves.keys()].map(saveNow));

// ---------- deleting a chapter's notebook ----------
// Removes its notes and tables for good, after confirmation; the chapter is greyed again.
async function deleteNotebook() {
  const { book, chapter, verses } = current;
  const notes = verses.filter(v => v.note.trim()).length;
  const tables = verses.filter(v => v.table.length).length;
  const content = [notes && `${notes} note${notes > 1 ? "s" : ""}`, tables && `${tables} tableau${tables > 1 ? "x" : ""}`]
    .filter(Boolean).join(" et ");
  const question = `Supprimer le carnet ${reference(book, chapter)} ?\n\n` +
    (content ? `${content} ${notes + tables > 1 ? "seront supprimés" : "sera supprimé"} définitivement.` : "Ce carnet est vide.");
  if (!confirm(question)) return;

  // Drop this chapter's pending saves and let any save under way finish, so none lands afterwards.
  const inFlight = [];
  for (const [key, s] of saves) {
    if (s.book !== book || s.chapter !== chapter) continue;
    clearTimeout(s.timer);
    if (s.inFlight) { s.again = false; inFlight.push(s.inFlight); }
    saves.delete(key);
  }
  await Promise.all(inFlight);

  const r = await fetch(`/api/notebooks/${book}/${chapter}`, { method: "DELETE" });
  if (!r.ok && r.status !== 404) {
    alert(`Le carnet n'a pas pu être supprimé : ${(await r.json().catch(() => ({}))).error || r.status}`);
    return;
  }
  for (const part of toc.parts)
    for (const b of part.books)
      if (b.osis === book) b.created = b.created.filter(c => c !== chapter);
  current = null;
  history.pushState({}, "", location.pathname);
  document.title = "Benneria Notebook";
  renderToc();
  renderNotebook();
}

$("#view").addEventListener("click", (ev) => { if (ev.target.closest(".delete-notebook")) deleteNotebook(); });

// ---------- a verb table per verse ----------
// Shown on demand: "+ Tableau des verbes" adds one; it goes away with its last row. Cells are
// free text, saved like notes. Verbe and Racine are Hebrew (right to left).
const COLUMNS = {
  verb: "Verbe", root: "Racine", binyan: "Binyan", tense: "Temps", person: "Personne", translation: "Traduction",
};
const HEBREW_COLUMNS = new Set(["verb", "root"]);
const emptyRow = () => current.columns.map(() => "");

function tableView(v) {
  if (!v.table.length)
    return `<button type="button" class="add-table">+ Tableau des verbes</button><span class="save-status" aria-live="polite"></span>`;
  const cols = current.columns;
  return `<div class="table-scroll"><table class="verb-table">
      <thead><tr>${cols.map(c => `<th scope="col">${esc(COLUMNS[c] || c)}</th>`).join("")}<th><span class="visually-hidden">Actions</span></th></tr></thead>
      <tbody>${v.table.map((row, r) => `<tr data-row="${r}">${cols.map((c, i) => `<td>
          <input class="cell${HEBREW_COLUMNS.has(c) ? " he" : ""}" data-col="${i}" value="${esc(row[i])}"
            dir="${HEBREW_COLUMNS.has(c) ? "rtl" : "auto"}"${HEBREW_COLUMNS.has(c) ? ' lang="he"' : ""}
            aria-label="${esc(COLUMNS[c] || c)}, ligne ${r + 1}"></td>`).join("")}
          <td class="row-actions"><button type="button" class="remove-row" title="Supprimer la ligne" aria-label="Supprimer la ligne ${r + 1}">×</button></td>
        </tr>`).join("")}</tbody>
    </table></div>
    <div class="table-actions"><button type="button" class="add-row">+ Ligne</button><span class="save-status" aria-live="polite"></span></div>`;
}

function saveTable(verse, delay) {
  const { book, chapter } = current;
  queueSave({ kind: "tables", book, chapter, verse }, { rows: verseOf(verse).table }, delay);
}

// Redraw one verse's table, then put the cursor in the given cell.
function redrawTable(verse, focus) {
  const box = document.querySelector(`.verb-table-box[data-verse="${verse}"]`);
  box.innerHTML = tableView(verseOf(verse));
  if (focus) box.querySelector(`tr[data-row="${focus.row}"] input[data-col="${focus.col}"]`)?.focus();
}

$("#view").addEventListener("click", (ev) => {
  const box = ev.target.closest(".verb-table-box");
  if (!box) return;
  const verse = Number(box.dataset.verse);
  const table = verseOf(verse).table;
  if (ev.target.closest(".add-table") || ev.target.closest(".add-row")) {
    table.push(emptyRow());
    redrawTable(verse, { row: table.length - 1, col: 0 });
    saveTable(verse, 0);
  } else if (ev.target.closest(".remove-row")) {
    table.splice(Number(ev.target.closest("tr").dataset.row), 1);
    redrawTable(verse);
    saveTable(verse, 0);
  }
});

$("#view").addEventListener("input", (ev) => {
  const cell = ev.target.closest(".cell");
  if (!cell) return;
  const verse = Number(cell.closest(".verb-table-box").dataset.verse);
  verseOf(verse).table[Number(cell.closest("tr").dataset.row)][Number(cell.dataset.col)] = cell.value;
  saveTable(verse);
});

// Enter moves down a row in the same column, adding a row from the last one.
$("#view").addEventListener("keydown", (ev) => {
  const cell = ev.target.closest(".cell");
  if (!cell || ev.key !== "Enter") return;
  ev.preventDefault();
  const verse = Number(cell.closest(".verb-table-box").dataset.verse);
  const table = verseOf(verse).table;
  const row = Number(cell.closest("tr").dataset.row), col = Number(cell.dataset.col);
  if (row === table.length - 1) { table.push(emptyRow()); redrawTable(verse, { row: row + 1, col }); saveTable(verse, 0); }
  else cell.closest("tbody").querySelector(`tr[data-row="${row + 1}"] input[data-col="${col}"]`).focus();
});

// Leaving a table saves it at once.
$("#view").addEventListener("focusout", (ev) => {
  const box = ev.target.closest(".verb-table-box");
  if (box && !box.contains(ev.relatedTarget))
    saveNow(saveKey("tables", current.book, current.chapter, Number(box.dataset.verse)));
});

$("#view").addEventListener("click", (ev) => {
  const view = ev.target.closest(".note-view");
  if (view && !ev.target.closest("a")) startEditing(view.closest(".verse-note"));
});
$("#view").addEventListener("keydown", (ev) => {
  const view = ev.target.closest(".note-view");
  if (view && (ev.key === "Enter" || ev.key === " ")) { ev.preventDefault(); startEditing(view.closest(".verse-note")); }
});
window.addEventListener("beforeunload", (ev) => { if (saves.size) { ev.preventDefault(); ev.returnValue = ""; } });

// ---------- options, history, start ----------
$("#names").addEventListener("change", async () => {
  await flushNotes();
  names = $("#names").value;
  try { localStorage.setItem(NAMES_KEY, names); } catch {}
  renderToc();
  renderNotebook();
});

function route(push) {
  const m = new URLSearchParams(location.search).get("c")?.match(/^(\w+)\.(\d+)$/);
  if (m) openNotebook(m[1], Number(m[2]), push);
  else { current = null; renderToc(); renderNotebook(); }
}
window.addEventListener("popstate", () => route(false));

(async () => {
  toc = await (await fetch("/api/toc")).json();
  route(false);
})();
