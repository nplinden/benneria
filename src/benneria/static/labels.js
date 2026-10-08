// Display names for the codes found in lexicon entries.

// Strong's part-of-speech key, from OpenScriptures' PartsOfSpeech.xml
// (https://github.com/openscriptures/HebrewLexicon/blob/master/PartsOfSpeech.xml).
const MORPH_NAMES = {
  "a": "Adjective", "a-f": "Adjective Feminine", "a-gent": "Gentilic Adjective",
  "a-m": "Adjective Masculine", "adv": "Adverb", "arbor": "Arbor", "comm": "Common",
  "conj": "Conjunction", "cstr": "Construct", "d": "Demonstrative Pronoun",
  "da": "Definite Article", "deae": "Deity", "dei": "Deity", "denom": "Denominative",
  "div": "Divine", "dp": "Demonstrative Particle", "du": "Dual",
  "enclitic part": "Enclitic Particle", "epith": "Epithet", "fl": "Flumen", "flum": "Flumen",
  "font": "Fountain", "indef": "Indefinite", "inj": "Interjection", "i": "Interrogative Pronoun",
  "mens": "Month", "mont": "Mountain", "np": "Negative Particle", "n": "Noun",
  "n-f": "Noun Feminine", "n-m": "Noun Masculine", "n-m-loc": "Noun Masculine Location",
  "n-pr": "Proper Name", "n-pr-f": "Proper Name Feminine", "n-pr-loc": "Proper Name Location",
  "n-pr-m": "Proper Name Masculine", "p": "Personal Pronoun", "pr": "Proper",
  "prep": "Preposition", "pron": "Pronoun", "prt": "Particle", "pt": "Participle",
  "putei": "Well", "r": "Relative Pronoun", "rpt": "Relative Particle", "rup": "Cliff",
  "sg": "Singular", "terr": "Territory", "trib": "Tribe", "urb": "City", "v": "Verb",
  "x": "Indefinite Pronoun",
};
// Some entries carry several codes separated by spaces, e.g. "n-pr-m n-pr-loc".
const morphName = (m) => !m ? "No morph" : MORPH_NAMES[m] ||
  m.split(/\s+/).map(t => MORPH_NAMES[t] || t).join(" / ");

// language_code values: ISO codes in BDB Augmented Strong, abbreviation fragments in Jastrow/Klein.
const LANG_NAMES = {
  "heb": "Hebrew", "arc": "Aramaic",
  "b. h.": "Biblical Hebrew", "ch.": "Aramaic", "PBH": "Post-Biblical Hebrew",
};
function langName(code) {
  if (!code || code === "x-pn") return "";  // x-pn marks a proper name, not a language
  const key = String(code).trim().replace(/^[(\s]+|[;,\s]+$/g, "");
  return LANG_NAMES[key] || key;
}

// OSHB morphology codes, used by morphhb parses ("HC/Vqw3mp") and by the Lexical Index part of
// speech ("N", "Np", "Td"). From https://hb.openscriptures.org/parsing/HebrewMorphologyCodes.html
const OSHB = {
  pos: { A: "Adjective", C: "Conjunction", D: "Adverb", N: "Noun", P: "Pronoun", R: "Preposition",
         S: "Suffix", T: "Particle", V: "Verb" },
  // Type names stand on their own ("Personal pronoun"); "" means the plain part of speech.
  types: {
    A: { a: "", c: "Cardinal number", g: "Gentilic adjective", o: "Ordinal number" },
    N: { c: "", g: "Gentilic noun", p: "Proper name" },
    P: { d: "Demonstrative pronoun", f: "Indefinite pronoun", i: "Interrogative pronoun",
         p: "Personal pronoun", r: "Relative pronoun" },
    R: { d: "Preposition with article" },
    S: { d: "Directional he", h: "Paragogic he", n: "Paragogic nun", p: "Pronominal suffix" },
    T: { a: "Affirmation particle", d: "Definite article", e: "Exhortation particle",
         i: "Interrogative particle", j: "Interjection", m: "Demonstrative particle",
         n: "Negative particle", o: "Direct object marker", r: "Relative particle" },
  },
  stems: {
    H: { q: "Qal", N: "Niphal", p: "Piel", P: "Pual", h: "Hiphil", H: "Hophal", t: "Hithpael",
         o: "Polel", O: "Polal", r: "Hithpolel", m: "Poel", M: "Poal", k: "Palel", K: "Pulal",
         Q: "Qal passive", l: "Pilpel", L: "Polpal", f: "Hithpalpel", D: "Nithpael", j: "Pealal",
         i: "Pilel", u: "Hothpaal", c: "Tiphil", v: "Hishtaphel", w: "Nithpalel", y: "Nithpoel",
         z: "Hithpoel" },
    A: { q: "Peal", Q: "Peil", u: "Hithpeel", p: "Pael", P: "Ithpaal", M: "Hithpaal", a: "Aphel",
         h: "Haphel", s: "Saphel", e: "Shaphel", H: "Hophal", i: "Ithpeel", t: "Hishtaphel",
         v: "Ishtaphel", w: "Hithaphel", o: "Polel", z: "Ithpoel", r: "Hithpolel", f: "Hithpalpel",
         b: "Hephal", c: "Tiphel", m: "Poel", l: "Palpel", L: "Ithpalpel", O: "Ithpolel", G: "Ittaphal" },
  },
  conj: { p: "perfect (qatal)", q: "sequential perfect (weqatal)", i: "imperfect (yiqtol)",
          w: "sequential imperfect (wayyiqtol)", h: "cohortative", j: "jussive", v: "imperative",
          r: "active participle", s: "passive participle", a: "infinitive absolute", c: "infinitive construct" },
  person: { 1: "1st", 2: "2nd", 3: "3rd" },
  gender: { b: "both genders", c: "common", f: "feminine", m: "masculine" },
  number: { d: "dual", p: "plural", s: "singular" },
  state: { a: "absolute", c: "construct", d: "determined" },
};

// Lexical Index part of speech: "Np" -> "Proper name", "Td" -> "Definite article", "R C" ->
// "Preposition / Conjunction". A trailing "?" is kept.
function posName(code) {
  if (!code) return "";
  return code.split(/\s+/).map(c => {
    const [p, t] = [c[0], c[1]];
    const type = t && OSHB.types[p] ? OSHB.types[p][t] : "";
    return (type || OSHB.pos[p] || c) + (c.endsWith("?") ? "?" : "");
  }).join(" / ");
}

// One part of a parse, without the language letter: "Vqw3mp", "Ncfsa", "Sp3mp", "Td".
function parsePart(seg, lang) {
  const p = seg[0], rest = seg.slice(1).split("");
  const name = OSHB.pos[p] || seg;
  const fields = [];
  const take = (table) => { const v = rest.shift(); if (v && v !== "x" && table[v]) fields.push(table[v]); };
  if (p === "V") {
    const stem = rest.shift(), conj = rest.shift();
    const head = [(OSHB.stems[lang] || OSHB.stems.H)[stem] || stem, OSHB.conj[conj] || conj].filter(Boolean).join(" ");
    if (conj === "r" || conj === "s") { take(OSHB.gender); take(OSHB.number); take(OSHB.state); }
    else if (conj !== "a" && conj !== "c") { take(OSHB.person); take(OSHB.gender); take(OSHB.number); }
    return head + (fields.length ? ", " + fields.join(" ") : "");
  }
  let label = name;
  if (OSHB.types[p] && rest.length) label = OSHB.types[p][rest.shift()] || name;
  if (p === "A" || p === "N") { take(OSHB.gender); take(OSHB.number); take(OSHB.state); }
  if (p === "P" || p === "S") { take(OSHB.person); take(OSHB.gender); take(OSHB.number); }
  return label + (fields.length ? ", " + fields.join(" ") : "");
}

// A full morphhb parse: "HC/Vqw3mp" -> "Conjunction + Qal sequential imperfect (wayyiqtol), 3rd masculine plural".
function parseName(morph) {
  if (!morph) return "";
  const lang = morph[0] === "A" ? "A" : "H";
  return morph.slice(1).split("/").map(s => parsePart(s, lang)).join(" + ");
}
