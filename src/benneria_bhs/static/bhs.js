const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c =>
  ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));

let books = [];   // [{osis, chapters}], in canonical order (from /api/toc, ignoring "created")
let current = null;   // {book, chapter}

const bookName = (osis) => (BOOK_NAMES[osis] || {}).en || osis;

function populateBooks() {
  $("#book").innerHTML = books.map(b => `<option value="${b.osis}">${esc(bookName(b.osis))}</option>`).join("");
}

function populateChapters(osis) {
  const book = books.find(b => b.osis === osis);
  const n = book ? book.chapters : 1;
  $("#chapter").innerHTML = Array.from({ length: n }, (_, i) => i + 1)
    .map(c => `<option value="${c}">${c}</option>`).join("");
}

async function openChapter(book, chapter, push = true) {
  $("#book").value = book;
  populateChapters(book);
  $("#chapter").value = chapter;
  try {
    const r = await fetch(`/api/bhs/${book}/${chapter}`);
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
    current = { book, chapter };
    if (push) history.pushState({ book, chapter }, "", `?c=${book}.${chapter}`);
    render(data);
  } catch (err) {
    $("#view").innerHTML = `<p class="status error">${esc(err.message)}</p>`;
  }
}

function render(data) {
  const { book, chapter, verses } = data;
  document.title = `${bookName(book)} ${chapter} · Benneria BHS`;
  $("#view").innerHTML = `
    <h1 class="chapter-title">${esc(bookName(book))} ${chapter}</h1>
    ${verses.map(v => `
      <section class="admonition" id="v${v.verse}">
        <div class="admonition-head"><span aria-hidden="true">✦</span> ${bookName(book)} ${chapter}:${v.verse}</div>
        <p class="verse-text he" dir="rtl" lang="he">${esc(v.text)}</p>
      </section>`).join("")}`;
  window.scrollTo({ top: 0 });
}

$("#book").addEventListener("change", () => {
  populateChapters($("#book").value);
  openChapter($("#book").value, 1);
});
$("#chapter").addEventListener("change", () => openChapter($("#book").value, Number($("#chapter").value)));

function route(push) {
  const m = new URLSearchParams(location.search).get("c")?.match(/^(\w+)\.(\d+)$/);
  const [book, chapter] = m ? [m[1], Number(m[2])] : [books[0].osis, 1];
  openChapter(book, chapter, push);
}
window.addEventListener("popstate", () => route(false));

(async () => {
  const toc = await (await fetch("/api/toc")).json();
  books = toc.parts.flatMap(p => p.books);
  populateBooks();
  route(false);
})();
