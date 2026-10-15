// A small Markdown renderer for notes. The text is HTML-escaped first, so only the markup below
// can produce HTML, and nothing typed in a note can inject code into the page.
//
// Blocks (separated by a blank line): paragraphs (single line breaks kept), # / ## / ### headings,
// "> " quotes, "- " or "* " lists, "1. " lists, and a line of three dashes (---) as a rule.
// Inline: **bold**, *italic* or _italic_, `code`, [text](https://link).
// Each block is dir="auto", so a Hebrew paragraph runs right to left.

function renderMarkdown(source) {
  const escape = (s) => s.replace(/[&<>"']/g, c =>
    ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));

  function inline(text) {
    const codes = [];
    let s = escape(text).replace(/`([^`]+)`/g, (_, code) => `\u0000${codes.push(code) - 1}\u0000`);
    s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      (_, label, url) => `<a href="${url}" target="_blank" rel="noopener">${label}</a>`);
    s = s.replace(/\*\*(?=\S)([\s\S]*?\S)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/(^|[^*\w])\*(?=\S)([^*]*?\S)\*(?!\*)/g, "$1<em>$2</em>");
    s = s.replace(/(^|[^_\w])_(?=\S)([^_]*?\S)_(?![_\w])/g, "$1<em>$2</em>");
    return s.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${codes[i]}</code>`);
  }

  const blocks = source.replace(/\r\n?/g, "\n").split(/\n\s*\n/);
  return blocks.map(block => {
    const lines = block.split("\n").filter((l, i, all) => l.trim() || all.length === 1);
    if (!lines.length || !block.trim()) return "";
    let m;
    if (lines.length === 1 && /^\s*-{3,}\s*$/.test(lines[0])) return "<hr>";
    if ((m = lines[0].match(/^(#{1,3})\s+(.*)$/)) && lines.length === 1)
      return `<h${m[1].length + 2} dir="auto">${inline(m[2])}</h${m[1].length + 2}>`;
    if (lines.every(l => /^\s*>\s?/.test(l)))
      return `<blockquote dir="auto">${lines.map(l => inline(l.replace(/^\s*>\s?/, ""))).join("<br>")}</blockquote>`;
    if (lines.every(l => /^\s*[-*]\s+/.test(l)))
      return `<ul dir="auto">${lines.map(l => `<li>${inline(l.replace(/^\s*[-*]\s+/, ""))}</li>`).join("")}</ul>`;
    if (lines.every(l => /^\s*\d+[.)]\s+/.test(l)))
      return `<ol dir="auto">${lines.map(l => `<li>${inline(l.replace(/^\s*\d+[.)]\s+/, ""))}</li>`).join("")}</ol>`;
    return `<p dir="auto">${lines.map(inline).join("<br>")}</p>`;
  }).join("");
}
