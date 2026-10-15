// Names of the books and parts of the Hebrew Bible, by OSIS code, in French (default), English
// and Hebrew. French names follow the French Rabbinate's translation (as in hegram).
const BOOK_NAMES = {
  Gen:   { fr: "Genèse", en: "Genesis", he: "בראשית" },
  Exod:  { fr: "Exode", en: "Exodus", he: "שמות" },
  Lev:   { fr: "Lévitique", en: "Leviticus", he: "ויקרא" },
  Num:   { fr: "Nombres", en: "Numbers", he: "במדבר" },
  Deut:  { fr: "Deutéronome", en: "Deuteronomy", he: "דברים" },
  Josh:  { fr: "Josué", en: "Joshua", he: "יהושע" },
  Judg:  { fr: "Juges", en: "Judges", he: "שופטים" },
  "1Sam": { fr: "1 Samuel", en: "1 Samuel", he: "שמואל א" },
  "2Sam": { fr: "2 Samuel", en: "2 Samuel", he: "שמואל ב" },
  "1Kgs": { fr: "1 Rois", en: "1 Kings", he: "מלכים א" },
  "2Kgs": { fr: "2 Rois", en: "2 Kings", he: "מלכים ב" },
  Isa:   { fr: "Isaïe", en: "Isaiah", he: "ישעיהו" },
  Jer:   { fr: "Jérémie", en: "Jeremiah", he: "ירמיהו" },
  Ezek:  { fr: "Ézéchiel", en: "Ezekiel", he: "יחזקאל" },
  Hos:   { fr: "Osée", en: "Hosea", he: "הושע" },
  Joel:  { fr: "Joël", en: "Joel", he: "יואל" },
  Amos:  { fr: "Amos", en: "Amos", he: "עמוס" },
  Obad:  { fr: "Obadia", en: "Obadiah", he: "עובדיה" },
  Jonah: { fr: "Jonas", en: "Jonah", he: "יונה" },
  Mic:   { fr: "Michée", en: "Micah", he: "מיכה" },
  Nah:   { fr: "Nahoum", en: "Nahum", he: "נחום" },
  Hab:   { fr: "Habacuc", en: "Habakkuk", he: "חבקוק" },
  Zeph:  { fr: "Cephania", en: "Zephaniah", he: "צפניה" },
  Hag:   { fr: "Haggaï", en: "Haggai", he: "חגי" },
  Zech:  { fr: "Zacharie", en: "Zechariah", he: "זכריה" },
  Mal:   { fr: "Malachie", en: "Malachi", he: "מלאכי" },
  Ps:    { fr: "Psaumes", en: "Psalms", he: "תהלים" },
  Job:   { fr: "Job", en: "Job", he: "איוב" },
  Prov:  { fr: "Proverbes", en: "Proverbs", he: "משלי" },
  Ruth:  { fr: "Ruth", en: "Ruth", he: "רות" },
  Song:  { fr: "Cantique des Cantiques", en: "Song of Songs", he: "שיר השירים" },
  Eccl:  { fr: "Ecclésiaste", en: "Ecclesiastes", he: "קהלת" },
  Lam:   { fr: "Lamentations", en: "Lamentations", he: "איכה" },
  Esth:  { fr: "Esther", en: "Esther", he: "אסתר" },
  Dan:   { fr: "Daniel", en: "Daniel", he: "דניאל" },
  Ezra:  { fr: "Ezra", en: "Ezra", he: "עזרא" },
  Neh:   { fr: "Néhémie", en: "Nehemiah", he: "נחמיה" },
  "1Chr": { fr: "1 Chroniques", en: "1 Chronicles", he: "דברי הימים א" },
  "2Chr": { fr: "2 Chroniques", en: "2 Chronicles", he: "דברי הימים ב" },
};

const PART_NAMES = {
  torah:   { fr: "Torah", en: "Torah", he: "תורה" },
  neviim:  { fr: "Neviim", en: "Nevi'im", he: "נביאים" },
  ketuvim: { fr: "Ketouvim", en: "Ketuvim", he: "כתובים" },
};

// Chapter and verse numbers as Hebrew numerals (gematria): 6 → ו, 15 → טו, 150 → קנ.
function hebrewNumeral(n) {
  const ones = ["", "א", "ב", "ג", "ד", "ה", "ו", "ז", "ח", "ט"];
  const tens = ["", "י", "כ", "ל", "מ", "נ", "ס", "ע", "פ", "צ"];
  const hundreds = ["", "ק", "ר", "ש", "ת"];
  let out = hundreds[Math.floor(n / 100)] || "";
  n %= 100;
  if (n === 15) return out + "טו";  // not יה / יו, which spell divine names
  if (n === 16) return out + "טז";
  return out + tens[Math.floor(n / 10)] + ones[n % 10];
}
