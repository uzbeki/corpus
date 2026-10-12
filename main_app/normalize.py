"""Shared text normalization for corpus statistics and search.

The corpus mixes several glyphs for the Uzbek apostrophe (O'zbekiston,
Oʻzbekiston, O‘zbekiston, ...) and occasionally Cyrillic look-alike letters
inside Latin words (Cyrillic "А" in "Аmmo"). Stored text is never rewritten;
these helpers only build comparison keys and display forms.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

APOSTROPHE_VARIANTS = (
    "’",  # U+2019 right single quotation mark
    "‘",  # U+2018 left single quotation mark
    "ʼ",  # U+02BC modifier letter apostrophe
    "ʻ",  # U+02BB modifier letter turned comma (official Uzbek oʻ/gʻ)
    "ʽ",  # U+02BD modifier letter reversed comma
    "ʹ",  # U+02B9 modifier letter prime
    "′",  # U+2032 prime
    "‛",  # U+201B single high-reversed-9 quotation mark
    "´",  # U+00B4 acute accent
    "`",  # grave accent
    "＇",  # U+FF07 fullwidth apostrophe
)
_APOSTROPHE_TRANSLATION = str.maketrans({ch: "'" for ch in APOSTROPHE_VARIANTS})

# Cyrillic letters that render identically to Latin ones.
CYRILLIC_HOMOGLYPHS = {
    "А": "A", "а": "a", "В": "B", "Е": "E", "е": "e", "К": "K", "М": "M",
    "Н": "H", "О": "O", "о": "o", "Р": "P", "р": "p", "С": "C", "с": "c",
    "Т": "T", "у": "y", "Х": "X", "х": "x", "І": "I", "і": "i", "Ј": "J",
    "ј": "j", "Ѕ": "S", "ѕ": "s",
}
_HOMOGLYPH_TRANSLATION = str.maketrans(CYRILLIC_HOMOGLYPHS)

# Case-symmetric fold used for the database prefilter (Postgres TRANSLATE). It is a
# superset of the Python normalization, so anything search_word matches survives it.
_SEARCH_FOLD = {ch: "'" for ch in APOSTROPHE_VARIANTS}
for _cyr, _lat in CYRILLIC_HOMOGLYPHS.items():
    _SEARCH_FOLD[_cyr.upper()] = _lat.upper()
    _SEARCH_FOLD[_cyr.lower()] = _lat.lower()
_SEARCH_FOLD_TRANSLATION = str.maketrans(_SEARCH_FOLD)

INVISIBLE_CHARS = "\u00ad\u200b\u200c\u200d\u2060\ufeff"  # soft hyphen, zero-width chars, BOM
_INVISIBLE_RE = re.compile(f"[{INVISIBLE_CHARS}]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_CYRILLIC_RE = re.compile("[\u0400-\u04ff]")
_EDGE_PUNCT = " \t\r\n.,;:!?«»\"“”„"
# Leading/trailing non-word characters (annotation markers, brackets, quotes, punctuation).
_EDGE_NON_WORD_RE = re.compile(r"^[\W_]+|[\W_]+$")
SENTENCE_END_RE = re.compile(r"[.!?…]['\"”»)]*$")
# Punctuation glued to the next word ("qildi.Toshkent", "yetmay,nopoklik"). Digits on
# the left are excluded so numbers like 3.5 or 1,200 stay whole.
_GLUED_PUNCT_RE = re.compile(r"(?<=[^\d\W][.,;:!?/])(?=[^\W\d_]|[$\[\^(«“\"])")

# Characters past the end of SEARCH_FOLD_TO are deleted by TRANSLATE. Hyphens are
# dropped because word cleaning joins compounds (xotin-qizlar -> xotinqizlar).
SEARCH_FOLD_FROM = "".join(_SEARCH_FOLD) + INVISIBLE_CHARS + "-\u2011"
SEARCH_FOLD_TO = "".join(_SEARCH_FOLD.values())


def normalize_apostrophes(value: str) -> str:
    """Map every apostrophe-like glyph to a plain ASCII apostrophe."""

    return (value or "").translate(_APOSTROPHE_TRANSLATION)


def fold_homoglyphs(token: str) -> str:
    """Replace Cyrillic look-alikes with Latin letters in mixed-script tokens.

    Purely Cyrillic tokens are left alone so genuine Cyrillic text is not mangled.
    """

    if _CYRILLIC_RE.search(token) and _LATIN_RE.search(token):
        return token.translate(_HOMOGLYPH_TRANSLATION)
    return token


def search_fold(value: str) -> str:
    """Python equivalent of the database prefilter fold."""

    value = re.sub("[-\u2011]", "", _INVISIBLE_RE.sub("", value or ""))
    return value.translate(_SEARCH_FOLD_TRANSLATION)


def split_tokens(text: str) -> list[str]:
    """Split text into word tokens on whitespace and on punctuation glued to the next word."""

    tokens = []
    for chunk in (text or "").split():
        tokens.extend(part for part in _GLUED_PUNCT_RE.split(chunk) if part)
    return tokens


def normalize_text(value: str) -> str:
    """Normalize apostrophes, invisible characters and mixed-script tokens."""

    text = unicodedata.normalize("NFC", value or "")
    text = _INVISIBLE_RE.sub("", text)
    text = normalize_apostrophes(text)
    return re.sub(r"\S+", lambda m: fold_homoglyphs(m.group(0)), text)


def normalize_name(value: str) -> str:
    """Display form for an annotated name: normalized text, single spaces, no edge punctuation."""

    text = " ".join(normalize_text(value).split())
    return text.strip(_EDGE_PUNCT)


def name_key(value: str) -> str:
    """Grouping key for annotated names: case-insensitive normalized form."""

    return normalize_name(value).casefold()


def word_core(token: str) -> str:
    """Lower-cased word with annotation markers and edge punctuation removed.

    Expects text that already went through ``normalize_text``.
    """

    return _EDGE_NON_WORD_RE.sub("", token).strip("'").lower()


class NameTally:
    """Count annotated names by (kind, normalized key), keeping the most common display form."""

    def __init__(self):
        self.counts: Counter = Counter()
        self.forms: dict[tuple[str, str], Counter] = {}

    def add(self, kind: str, raw_name: str) -> None:
        display = normalize_name(raw_name)
        if not display:
            return
        key = (kind, display.casefold())
        self.counts[key] += 1
        self.forms.setdefault(key, Counter())[display] += 1

    def display_name(self, key: tuple[str, str]) -> str:
        # Most frequent surface form wins; ties resolve alphabetically for stable output.
        forms = self.forms[key]
        return min(forms, key=lambda form: (-forms[form], form))

    def frequency(self, kinds: set[str] | None = None) -> list[dict]:
        items = [
            {"name": self.display_name(key), "gender": key[0], "count": count}
            for key, count in self.counts.items()
            if kinds is None or key[0] in kinds
        ]
        items.sort(key=lambda x: (-x["count"], x["name"]))
        return items
