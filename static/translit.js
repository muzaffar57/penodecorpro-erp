/* ============================================================
   O'ZBEKCHA LOTIN <-> KIRILL — brauzer uchun tarjima dvigateli
   ============================================================
   MUHIM: bu fayl, avval PYTHON'da qurilib, PUXTA sinalgan mantiqning
   ANIQ, so'zma-so'z ko'chirmasi — mustaqil, yangi mantiq EMAS.
   (2026-09) — apostrof va kod-himoyasi masalalari, alohida sinovdan
   o'tkazilgan.
*/

// ── 1) APOSTROF BELGILARINI, BITTA KO'RINISHGA KELTIRISH ──
// MUHIM: bu belgilar, ko'rinishda bir-biriga JUDA o'xshaydi, lekin,
// har biri, ALOHIDA Unicode kodi — shuning uchun, \uXXXX orqali,
// ANIQ yozilgan (oddiy ko'chirib-yopishtirish EMAS).
const APOSTROPHE_VARIANTS = [
  "\u2019", // ' RIGHT SINGLE QUOTATION MARK — eng ko'p ishlatiladigan
  "\u2018", // ' LEFT SINGLE QUOTATION MARK
  "\u02BB", // ʻ MODIFIER LETTER TURNED COMMA — rasmiy o'zbekcha
  "\u02BC", // ʼ MODIFIER LETTER APOSTROPHE
  "\u0060", // ` GRAVE ACCENT
  "\u00B4", // ´ ACUTE ACCENT
  "\u2032", // ′ PRIME
];

function normalizeApostrophes(text) {
  let result = text;
  for (const variant of APOSTROPHE_VARIANTS) {
    result = result.split(variant).join("'");
  }
  return result;
}

// ── 2) LOTIN -> KIRILL ──
// MUHIM: TARTIB — uzunroq (ko'p harfli) birikmalar, DOIM birinchi
// tekshirilishi kerak (masalan "sh", "o'"), aks holda, ular,
// ALOHIDA-ALOHIDA o'girilib qolishi mumkin.
const LAT2CYR_MULTI = [
  ["o'", "ў"], ["O'", "Ў"],
  ["g'", "ғ"], ["G'", "Ғ"],
  ["sh", "ш"], ["Sh", "Ш"], ["SH", "Ш"],
  ["ch", "ч"], ["Ch", "Ч"], ["CH", "Ч"],
  ["yo", "ё"], ["Yo", "Ё"], ["YO", "Ё"],
  ["yu", "ю"], ["Yu", "Ю"], ["YU", "Ю"],
  ["ya", "я"], ["Ya", "Я"], ["YA", "Я"],
];

const LAT2CYR_SINGLE = {
  "a": "а", "A": "А", "b": "б", "B": "Б", "d": "д", "D": "Д",
  "e": "е", "E": "Е", "f": "ф", "F": "Ф", "g": "г", "G": "Г",
  "h": "ҳ", "H": "Ҳ", "i": "и", "I": "И", "j": "ж", "J": "Ж",
  "k": "к", "K": "К", "l": "л", "L": "Л", "m": "м", "M": "М",
  "n": "н", "N": "Н", "o": "о", "O": "О", "p": "п", "P": "П",
  "q": "қ", "Q": "Қ", "r": "р", "R": "Р", "s": "с", "S": "С",
  "t": "т", "T": "Т", "u": "у", "U": "У", "v": "в", "V": "В",
  "x": "х", "X": "Х", "y": "й", "Y": "Й", "z": "з", "Z": "З",
};

// MUHIM: "ORD-028-1", "DEL-005" kabi, KOD ko'rinishidagi so'zlar —
// ATAYLAB, o'zgartirilmaydi (aks holda, buyurtma raqamlari buzilib
// qolardi). Naqsh: 2-6 ta katta lotin harf, chiziqcha, keyin
// raqam/harf/chiziqcha aralashmasi.
const CODE_PATTERN = /^[A-Z]{2,6}-[\dA-Z-]+$/;

function convertLatinToken(token) {
  if (CODE_PATTERN.test(token)) {
    return token; // Kod — o'zgarishsiz
  }
  let t = normalizeApostrophes(token);
  for (const [lat, cyr] of LAT2CYR_MULTI) {
    t = t.split(lat).join(cyr);
  }
  let result = "";
  for (const ch of t) {
    result += (LAT2CYR_SINGLE[ch] !== undefined) ? LAT2CYR_SINGLE[ch] : ch;
  }
  return result;
}

/**
 * Lotin -> Kirill. Raqamlar, tinish belgilari, buyurtma kodlari —
 * o'zgarishsiz qoladi.
 */
function latinToCyrillic(text) {
  if (!text) return text;
  // So'zlarni, bo'sh joylardan foydalanib ajratamiz, lekin o'sha
  // ajratuvchi belgilarning o'zini ham SAQLAB QOLAMIZ.
  const parts = text.split(/(\s+)/);
  return parts.map(p => (p.trim() ? convertLatinToken(p) : p)).join("");
}

// ── 3) KIRILL -> LOTIN (teskari, saqlash uchun) ──
const CYR2LAT_SINGLE = {
  "а": "a", "А": "A", "б": "b", "Б": "B", "в": "v", "В": "V",
  "г": "g", "Г": "G", "д": "d", "Д": "D", "е": "e", "Е": "E",
  "ё": "yo", "Ё": "Yo", "ж": "j", "Ж": "J", "з": "z", "З": "Z",
  "и": "i", "И": "I", "й": "y", "Й": "Y", "к": "k", "К": "K",
  "л": "l", "Л": "L", "м": "m", "М": "M", "н": "n", "Н": "N",
  "о": "o", "О": "O", "п": "p", "П": "P", "р": "r", "Р": "R",
  "с": "s", "С": "S", "т": "t", "Т": "T", "у": "u", "У": "U",
  "ф": "f", "Ф": "F", "х": "x", "Х": "X", "ц": "s", "Ц": "S",
  "ч": "ch", "Ч": "Ch", "ш": "sh", "Ш": "Sh", "щ": "sh", "Щ": "Sh",
  "ъ": "", "Ъ": "", "ы": "i", "Ы": "I", "ь": "", "Ь": "",
  "э": "e", "Э": "E", "ю": "yu", "Ю": "Yu", "я": "ya", "Я": "Ya",
  "қ": "q", "Қ": "Q", "ғ": "g'", "Ғ": "G'", "ў": "o'", "Ў": "O'",
  "ҳ": "h", "Ҳ": "H",
};

/**
 * Kirill -> Lotin (bazaga YOZISHDAN OLDIN, formalarga kiritilgan
 * matnni, avtomatik ravishda lotinga o'girish uchun ishlatiladi).
 */
function cyrillicToLatin(text) {
  if (!text) return text;
  let result = "";
  for (const ch of text) {
    result += (CYR2LAT_SINGLE[ch] !== undefined) ? CYR2LAT_SINGLE[ch] : ch;
  }
  return result;
}

// Node.js orqali sinash uchun (brauzerda, bu qism ishlamaydi/kerak emas)
if (typeof module !== "undefined" && module.exports) {
  module.exports = { latinToCyrillic, cyrillicToLatin };
}
