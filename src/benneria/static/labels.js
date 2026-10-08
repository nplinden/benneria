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
