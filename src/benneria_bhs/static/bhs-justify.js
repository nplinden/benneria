// Justifies the BHS reader's text by widening the gaps after a sof pasuq (׃) first, keeping the
// space between words even, instead of the browser's justification, which spreads each line's
// leftover width evenly over all its spaces.
//
// The text keeps every space character as it is: each one is wrapped in a span (.vgap after a sof
// pasuq, .ws between words) and only its word-spacing changes. So selecting, copying and searching
// the text are unaffected.
//
// For each line except a paragraph's last: the leftover width goes to its verse gaps, up to
// GAP_CAP normal spaces each; whatever remains (or all of it, on a line with no verse gap) is
// shared by its word spaces. Without JavaScript, or when printing, the CSS justification applies.

const GAP_CAP = 4;      // a verse gap grows to at most this many times a normal space
const SAFETY = 1;       // px left unused per line, so rounding never pushes a word to the next line

function justifyBhs(container) {
  if (!container) return;
  const spaces = [...container.querySelectorAll(".vgap, .ws")];
  // Measure the natural layout: no extra spacing, browser justification off.
  container.classList.add("js-justify");
  for (const s of spaces) s.style.wordSpacing = "";
  if (!spaces.length) return;

  const box = container.getBoundingClientRect();
  const spaceWidth = spaces.find(s => s.classList.contains("ws"))?.getBoundingClientRect().width || 6;

  const range = document.createRange();
  range.selectNodeContents(container);
  const lines = textLines(range);

  // Each space on its line. A space where the line breaks is left alone: it doesn't show.
  for (const s of spaces) {
    const r = s.getBoundingClientRect();
    if (r.width < 0.5) continue;
    const mid = (r.top + r.bottom) / 2;
    const line = lines.find(l => mid > l.top && mid < l.bottom);
    if (!line || r.left <= line.left + 0.5 || r.right >= line.right - 0.5) continue;
    (s.classList.contains("vgap") ? line.gaps : line.words).push(s);
  }

  // Share each line's leftover width; all measurements done first, then all changes.
  const widths = [];
  lines.forEach((line, i) => {
    if (i === lines.length - 1) return;  // the paragraph's last line stays as it is
    let slack = box.width - (line.right - line.left) - SAFETY;
    if (slack <= 0) return;
    if (line.gaps.length) {
      // capped, unless there are no word spaces to take the rest
      const extra = line.words.length ? Math.min(slack / line.gaps.length, spaceWidth * (GAP_CAP - 1)) : slack / line.gaps.length;
      for (const g of line.gaps) widths.push([g, extra]);
      slack -= extra * line.gaps.length;
    }
    if (slack > 0.5 && line.words.length) {
      const extra = slack / line.words.length;
      for (const w of line.words) widths.push([w, extra]);
    }
  });
  for (const [s, extra] of widths) s.style.wordSpacing = `${extra.toFixed(2)}px`;

  // If rounding still changed the line breaks, fall back to the browser's justification.
  if (textLines(range).length !== lines.length) {
    for (const s of spaces) s.style.wordSpacing = "";
    container.classList.remove("js-justify");
  }
}

// The text's lines: its fragments grouped by vertical position (a verse number, in a smaller font,
// is a fragment of its own on the same line), top to bottom.
function textLines(range) {
  const lines = [];
  for (const r of range.getClientRects()) {
    if (r.width < 0.5) continue;
    const mid = (r.top + r.bottom) / 2;
    let line = lines.find(l => mid > l.top && mid < l.bottom);
    if (!line) lines.push(line = { top: r.top, bottom: r.bottom, left: r.left, right: r.right, gaps: [], words: [] });
    line.top = Math.min(line.top, r.top);
    line.bottom = Math.max(line.bottom, r.bottom);
    line.left = Math.min(line.left, r.left);
    line.right = Math.max(line.right, r.right);
  }
  return lines.sort((a, b) => a.top - b.top);
}

// Re-justify when the text's width changes (window resize, zoom) or the fonts finish loading;
// at most once per frame.
let pending = 0;
function scheduleJustify() {
  cancelAnimationFrame(pending);
  pending = requestAnimationFrame(() => justifyBhs(document.querySelector(".bhs-text")));
}
let lastWidth = 0;
new ResizeObserver(entries => {
  const w = entries[0].contentRect.width;
  if (Math.abs(w - lastWidth) > 0.5) { lastWidth = w; scheduleJustify(); }
}).observe(document.querySelector("#view"));
document.fonts?.ready.then(scheduleJustify);
