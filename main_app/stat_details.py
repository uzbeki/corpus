"""Explanations and breakdowns shown when a statistics card is clicked.

Every builder returns plain JSON-serialisable dicts of the form::

    {
        "title": str,
        "description": str,
        "formula": str | None,
        "sections": [
            {"heading": str, "rows": [{"label", "value", "href"}]},
            {"heading": str, "chips": [{"label", "value", "href"}]},
        ],
        "note": str | None,
    }

which ``static/js/stat_details.js`` renders in a dialog.
"""

from __future__ import annotations

from urllib.parse import urlencode

from django.contrib.humanize.templatetags.humanize import intcomma
from django.urls import reverse

TOP_ITEMS = 10
HAPAX_EXAMPLES = 24

WORDS_METHOD = (
    "Words are whitespace-separated tokens after lower-casing, removing punctuation "
    "and annotation markers, and unifying apostrophe variants (O'zbekiston, Oʻzbekiston, "
    "O‘zbekiston are the same word)."
)
NAMES_METHOD = (
    "Counted from manual annotations in the article text: [Name] marks a male "
    "anthroponym, ^^Name^^ a female anthroponym and $$Place$$ a toponym. Spelling "
    "variants that differ only in apostrophe style or letter case are merged."
)


def search_url(query: str, language: int | None, **extra) -> str:
    params = {"q": query, "match_type": 1}
    if language:
        params["language"] = int(language)
    params.update({k: v for k, v in extra.items() if v not in (None, "")})
    return f"{reverse('search')}?{urlencode(params)}"


def segment_from_stats(
    label: str,
    language: int | None,
    word_stats: dict,
    name_stats: dict,
    *,
    article_count: int | None = None,
    downloads: dict | None = None,
) -> dict:
    """Condense full word/name statistics into what the detail dialogs need."""

    frequency = word_stats.get("frequency") or []
    hapax = sorted(
        item["word"]
        for item in frequency
        if item["count"] == 1 and not item["word"].isdigit()
    )
    names = [i for i in name_stats.get("frequency", []) if i["gender"] in {"male", "female"}]
    toponyms = [i for i in name_stats.get("frequency", []) if i["gender"] == "toponym"]
    return {
        "label": label,
        "language": int(language) if language else None,
        "article_count": article_count,
        "total_words": word_stats.get("total_words", 0),
        "unique_words": word_stats.get("unique_words", len(frequency)),
        "ttr": word_stats.get("ttr", 0),
        "hapax_count": word_stats.get("hapax_count", 0),
        "hapax_examples": hapax[:HAPAX_EXAMPLES],
        "top_words": frequency[:TOP_ITEMS],
        "name_counts": name_stats.get("counts", {}),
        "distinct_names": len(names),
        "distinct_toponyms": len(toponyms),
        "top_names": names[:TOP_ITEMS],
        "top_toponyms": toponyms[:TOP_ITEMS],
        "downloads": downloads or {},
    }


def _num(value) -> str:
    return intcomma(int(value or 0))


def _pct(part, whole) -> str:
    return f"{(part / whole * 100):.1f}%" if whole else "0%"


def _per_segment(segments, heading, value_fn) -> list[dict]:
    if len(segments) < 2:
        return []
    return [
        {
            "heading": heading,
            "rows": [{"label": s["label"], "value": value_fn(s)} for s in segments],
        }
    ]


def _download_rows(segments, kind, label) -> list[dict]:
    rows = [
        {"label": f"{label} ({s['label']})" if len(segments) > 1 else label,
         "value": "CSV", "href": s["downloads"][kind]}
        for s in segments
        if s["downloads"].get(kind)
    ]
    return [{"heading": "Download", "rows": rows}] if rows else []


def _chips(items, segment, search_extra, label_key="name", show_gender=False) -> list[dict]:
    chips = []
    for item in items:
        value = _num(item["count"])
        if show_gender:
            value = f"{item['gender']} · {value}"
        chips.append(
            {
                "label": item[label_key],
                "value": value,
                "href": search_url(item[label_key], segment["language"], **search_extra),
            }
        )
    return chips


def corpus_stat_details(
    segments: list[dict],
    *,
    scope: str,
    search_extra: dict | None = None,
    combined: dict | None = None,
) -> dict:
    """Details for word / lexical-diversity / annotation cards.

    `segments` holds one entry per language in scope. `combined` (optional)
    carries corpus-wide totals when segments are merged (e.g. the home page),
    where unique-word based metrics are not simple sums.
    """

    search_extra = search_extra or {}
    single = segments[0] if len(segments) == 1 else None
    combined = combined or {}
    multi_note = (
        "Unique words, TTR and hapax are computed on the merged vocabulary, so the "
        "per-language values do not add up to the overall figure."
        if len(segments) > 1
        else None
    )

    def top_word_sections():
        sections = []
        for s in segments:
            heading = "Most frequent words" + (f" · {s['label']}" if len(segments) > 1 else "")
            sections.append(
                {"heading": heading, "chips": _chips(s["top_words"], s, search_extra, "word")}
            )
        return sections

    total_words = combined.get("total_words", sum(s["total_words"] for s in segments))
    unique_words = combined.get(
        "unique_words", single["unique_words"] if single else sum(s["unique_words"] for s in segments)
    )
    ttr = combined.get("ttr", single["ttr"] if single else 0)
    hapax_count = combined.get("hapax_count", single["hapax_count"] if single else 0)

    details = {}

    details["words"] = {
        "title": "Words (tokens)",
        "description": f"Every running word in {scope}, repeats included. {WORDS_METHOD}",
        "formula": None,
        "sections": _per_segment(segments, "By language", lambda s: _num(s["total_words"]))
        + top_word_sections()
        + _download_rows(segments, "words", "Full word frequency list"),
        "note": None,
    }

    details["unique_words"] = {
        "title": "Unique words (types)",
        "description": f"Number of distinct word forms in {scope}. {WORDS_METHOD}",
        "formula": f"{_num(unique_words)} distinct forms out of {_num(total_words)} tokens",
        "sections": _per_segment(segments, "By language", lambda s: _num(s["unique_words"]))
        + top_word_sections(),
        "note": multi_note,
    }

    details["ttr"] = {
        "title": "Type-token ratio (TTR)",
        "description": (
            "Lexical diversity: the share of distinct word forms among all words. Closer to 1 "
            "means more varied vocabulary; it naturally drops as the text sample grows, so "
            "compare TTR only between samples of similar size."
        ),
        "formula": f"unique words ÷ total words = {_num(unique_words)} ÷ {_num(total_words)} = {ttr:.3f}",
        "sections": _per_segment(
            segments,
            "By language",
            lambda s: f"{s['ttr']:.3f}  ({_num(s['unique_words'])} ÷ {_num(s['total_words'])})",
        ),
        "note": multi_note,
    }

    hapax_sections = _per_segment(
        segments,
        "By language",
        lambda s: f"{_num(s['hapax_count'])}  ({_pct(s['hapax_count'], s['unique_words'])} of unique words)",
    )
    for s in segments:
        if not s["hapax_examples"]:
            continue
        heading = "Examples" + (f" · {s['label']}" if len(segments) > 1 else "")
        hapax_sections.append(
            {
                "heading": heading,
                "chips": [
                    {"label": word, "href": search_url(word, s["language"], **search_extra)}
                    for word in s["hapax_examples"]
                ],
            }
        )
    details["hapax"] = {
        "title": "Hapax legomena",
        "description": (
            f"Words that occur exactly once in {scope}. A high share of hapaxes indicates "
            "rich or specialised vocabulary (names, rare terms, typos)."
        ),
        "formula": f"{_num(hapax_count)} words = {_pct(hapax_count, unique_words)} of {_num(unique_words)} unique words",
        "sections": hapax_sections + _download_rows(segments, "words", "Full word frequency list"),
        "note": multi_note,
    }

    male = sum(s["name_counts"].get("male", 0) for s in segments)
    female = sum(s["name_counts"].get("female", 0) for s in segments)
    names_sections = [
        {
            "heading": "By gender",
            "rows": [
                {"label": "Male", "value": f"{_num(male)}  ({_pct(male, male + female)})"},
                {"label": "Female", "value": f"{_num(female)}  ({_pct(female, male + female)})"},
            ],
        }
    ]
    names_sections += _per_segment(
        segments, "By language", lambda s: _num(s["name_counts"].get("total", 0))
    )
    for s in segments:
        if s["top_names"]:
            heading = "Most frequent" + (f" · {s['label']}" if len(segments) > 1 else "")
            names_sections.append(
                {"heading": heading, "chips": _chips(s["top_names"], s, search_extra, show_gender=True)}
            )
    details["anthroponyms"] = {
        "title": "Annotated anthroponyms",
        "description": f"Personal names annotated in {scope} (every mention counts). {NAMES_METHOD}",
        "formula": (
            f"{_num(male)} male + {_num(female)} female = {_num(male + female)} mentions "
            f"of {_num(sum(s['distinct_names'] for s in segments))} distinct names"
        ),
        "sections": names_sections + _download_rows(segments, "names", "All anthroponyms"),
        "note": None,
    }

    toponym_total = sum(s["name_counts"].get("toponym", 0) for s in segments)
    toponym_sections = _per_segment(
        segments, "By language", lambda s: _num(s["name_counts"].get("toponym", 0))
    )
    for s in segments:
        if s["top_toponyms"]:
            heading = "Most frequent" + (f" · {s['label']}" if len(segments) > 1 else "")
            toponym_sections.append(
                {"heading": heading, "chips": _chips(s["top_toponyms"], s, search_extra)}
            )
    details["toponyms"] = {
        "title": "Toponyms",
        "description": f"Place names annotated in {scope} (every mention counts). {NAMES_METHOD}",
        "formula": (
            f"{_num(toponym_total)} mentions of "
            f"{_num(sum(s['distinct_toponyms'] for s in segments))} distinct places"
        ),
        "sections": toponym_sections + _download_rows(segments, "toponyms", "All toponyms"),
        "note": None,
    }

    return details


def article_count_details(
    *,
    scope: str,
    by_language: list[tuple[str, int]] | None = None,
    by_year: list[tuple[int, int]] | None = None,
    by_newspaper: list[tuple[str, int, str]] | None = None,
) -> dict:
    """Details for the Articles card: breakdowns with links to year/newspaper pages."""

    sections = []
    if by_language:
        sections.append(
            {"heading": "By language", "rows": [{"label": l, "value": _num(c)} for l, c in by_language]}
        )
    if by_newspaper:
        sections.append(
            {
                "heading": "By newspaper",
                "rows": [{"label": t, "value": _num(c), "href": href} for t, c, href in by_newspaper],
            }
        )
    if by_year:
        sections.append(
            {
                "heading": "By year",
                "rows": [
                    {
                        "label": str(year) if year else "Unknown",
                        "value": _num(count),
                        "href": reverse("year_archive", kwargs={"year": year}) if year else None,
                    }
                    for year, count in by_year
                ],
            }
        )
    return {
        "title": "Articles",
        "description": f"Number of articles in {scope}.",
        "formula": None,
        "sections": sections,
        "note": None,
    }


def newspaper_details(newspapers: list[dict]) -> dict:
    """Details for the Newspapers card. Each item: {"title", "href", "english", "uzbek"}."""

    return {
        "title": "Newspapers",
        "description": "Publications the corpus articles were collected from. Open one to see its own statistics.",
        "formula": None,
        "sections": [
            {
                "heading": "Articles per newspaper",
                "rows": [
                    {
                        "label": n["title"],
                        "value": f"{_num(n['english'] + n['uzbek'])}  (EN {_num(n['english'])} · UZ {_num(n['uzbek'])})",
                        "href": n["href"],
                    }
                    for n in newspapers
                ],
            }
        ],
        "note": None,
    }
