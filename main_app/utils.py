import nltk
import string
import re
from collections.abc import Iterable
from django.core.cache import cache
from django.db.models import Func, QuerySet
from main_app.counter import WordCounter, cleanse_word
from main_app.normalize import SENTENCE_END_RE, normalize_text, split_tokens, word_core
from main_app.types import Context, FrequencyStats, SearchResult, SearchResultItem

_PUNKT_READY = False
_PUNKT_RESOURCES = (
    ("tokenizers/punkt", "punkt"),
    ("tokenizers/punkt_tab/english", "punkt_tab"),
)


def ensure_punkt() -> None:
    """Load the tokenizer data only when tokenized search/stat helpers need it."""

    global _PUNKT_READY
    if _PUNKT_READY:
        return

    for resource_path, package_name in _PUNKT_RESOURCES:
        try:
            nltk.data.find(resource_path)
        except LookupError:
            nltk.download(package_name, quiet=True, raise_on_error=True)

    _PUNKT_READY = True


CORPUS_DASHBOARD_CACHE_KEY = "main_app:corpus_dashboard:v4"
CORPUS_DASHBOARD_CACHE_TIMEOUT = 60 * 60


def clear_corpus_dashboard_cache() -> None:
    """Clear cached corpus-wide dashboard data after article content changes."""

    cache.delete(CORPUS_DASHBOARD_CACHE_KEY)


def get_frequency_distribution(text: str, raw=False):
    """
    Get overall frequency distribution of a given text
    """
    if raw:
        fd = nltk.FreqDist(
            word.lower() for word in text.split() if word not in string.punctuation
        )
        return fd
    else:
        ensure_punkt()
        words = nltk.word_tokenize(text)

        # Calculate the frequency distribution with words punctuation removed
        freq_dist = nltk.FreqDist(
            word.lower() for word in words if word not in string.punctuation
        )
        # freq_dist = nltk.FreqDist(word.lower() for word in nltk.word_tokenize(sent))
        return freq_dist


def get_word_frequency(word: str, text: str):
    """
    Get word frequency of the article
    """
    freq_dist = get_frequency_distribution(text)
    return freq_dist[word]


class RegexpReplace(Func):
    r"""

    exaple RegexpReplace(
        'content',
        fr'((\S+\s+){{0,5}}\S*{substring}\S*(\s+\S+){{0,5}})',
        r'<mark>\1</mark>',
        'gi'  # 'gi' for case-insensitive matching
    )
    """

    function = "REGEXP_REPLACE"  # The name of the function in the database
    arity = 2  # The number of arguments the function takes


def _clean_context_marker_fragments(context: str) -> str:
    """Repair or remove fragmented annotation markers in snippet contexts."""

    cleaned = context or ""

    # Reconstruct split double markers produced by tokenization (e.g. "$ $" -> "$$").
    cleaned = re.sub(r"\$\s+\$", "$$", cleaned)
    cleaned = re.sub(r"\^\s+\^", "^^", cleaned)

    # If only one side of a double marker is present in the snippet, drop it.
    if cleaned.count("$$") % 2 != 0:
        cleaned = cleaned.replace("$$", "")
    if cleaned.count("^^") % 2 != 0:
        cleaned = cleaned.replace("^^", "")

    # Remove unmatched square brackets from clipped snippets.
    if cleaned.count("[") != cleaned.count("]"):
        cleaned = cleaned.replace("[", "").replace("]", "")

    # Remove leftover single marker chars (common in clipped/tokenized snippets).
    cleaned = re.sub(r"(?<!\$)\$(?!\$)", "", cleaned)
    cleaned = re.sub(r"(?<!\^)\^(?!\^)", "", cleaned)

    return re.sub(r"\s{2,}", " ", cleaned).strip()


def _core(token: str) -> str:
    """Match key for a token: the same cleaning the word statistics use, so a word
    from a frequency chart finds exactly the occurrences it was counted from. Tokens
    with no Latin letters/digits (e.g. Cyrillic) fall back to a looser form."""

    return cleanse_word(token) or word_core(token)


def query_cores(query: str) -> list[str]:
    return [core for core in (_core(t) for t in normalize_text(query).split()) if core]


def _match_type_at(cores: list[str], i: int, query: list[str]) -> str | None:
    """Return "exact"/"partial" if the query words match the tokens starting at i."""

    window = cores[i : i + len(query)]
    if len(window) < len(query) or not window[0]:
        return None
    if window == query:
        return "exact"
    if all(q in core for q, core in zip(query, window)):
        return "partial"
    return None


def _iter_matches(text: str, query: str):
    """Yield (tokens, cores, start, end, match_type) for each query match in text.

    Tokens come from split_tokens (whitespace plus glued punctuation) so Uzbek
    words such as ko'p stay intact and annotation markers ($$, ^^, [ ]) remain in
    the context for highlighting.
    """

    query_words = query_cores(query)
    # Content is plain text (templates escape it); "<" is often used as a quote mark.
    tokens = split_tokens(normalize_text(text or ""))
    if not query_words or not tokens:
        return
    cores = [_core(token) for token in tokens]
    i = 0
    while i < len(tokens):
        match_type = _match_type_at(cores, i, query_words)
        if match_type is None:
            i += 1
            continue
        end = i + len(query_words)
        yield tokens, cores, i, end, match_type
        i = end


def search_word(text: str, word: str, padding=5) -> SearchResultItem:
    """Find every occurrence of a word or phrase and return keyword-in-context snippets."""

    count = 0
    results = {"article": None, "frequency": 0, "locations": []}  # type: ignore
    for tokens, _cores, start, end, match_type in _iter_matches(text, word):
        count += 1
        context = " ".join(tokens[max(0, start - padding) : end + padding])
        results["locations"].append(
            Context(
                count=count,
                context=_clean_context_marker_fragments(context),
                type=match_type,
            )
        )
    results["frequency"] = count

    # sort locations that exact matches come first
    results["locations"].sort(key=lambda x: x["type"], reverse=False)
    return results


def find_ngrams(text: str, query: str, before: int, after: int, padding: int = 10) -> list[dict]:
    """Return the query match plus up to `before`/`after` neighbouring words.

    Neighbours never cross sentence boundaries, and punctuation-only tokens are
    skipped. Each item: {"left", "keyword", "right" (lists of word cores),
    "type", "context"}.
    """

    occurrences = []
    for tokens, _cores, start, end, match_type in _iter_matches(text, query):
        # Display forms keep hyphens (xotin-qizlar); punctuation-only tokens are skipped.
        left: list[str] = []
        j = start - 1
        while j >= 0 and len(left) < before and not SENTENCE_END_RE.search(tokens[j]):
            if word := word_core(tokens[j]):
                left.insert(0, word)
            j -= 1

        right: list[str] = []
        j = end
        # The keyword itself may end the sentence ("... kitob.").
        stop = bool(SENTENCE_END_RE.search(tokens[end - 1]))
        while not stop and j < len(tokens) and len(right) < after:
            if word := word_core(tokens[j]):
                right.append(word)
            stop = bool(SENTENCE_END_RE.search(tokens[j]))
            j += 1

        context = " ".join(tokens[max(0, start - padding) : end + padding])
        occurrences.append(
            {
                "left": left,
                "keyword": [word_core(token) for token in tokens[start:end]],
                "right": right,
                "type": match_type,
                "context": _clean_context_marker_fragments(context),
            }
        )
    return occurrences


# class FrequencyStat(TypedDict):
#     word: str
#     count: int
#     language: str

# FrequencyStats= list[FrequencyStat]


def _iter_contents(articles: QuerySet | Iterable) -> Iterable[str]:
    if isinstance(articles, QuerySet):
        return articles.values_list("content", flat=True).iterator(chunk_size=500)

    return ((getattr(article, "content", article) or "") for article in articles)


def aggregate_word_stats(articles: QuerySet | Iterable) -> dict:
    """Single pass word stats over a queryset.

    Returns:
        {
            "frequency": list[{"word", "count"}],
            "total_words": int,
            "unique_words": int,
            "ttr": float,
            "hapax_count": int,
        }
    """

    wc = WordCounter(_iter_contents(articles))

    frequency: FrequencyStats = [
        {"word": word, "count": count} for word, count in wc.word_freq.items()
    ]
    frequency.sort(key=lambda x: (-x["count"]))

    unique_words = len(wc.word_freq)
    hapax_count = sum(1 for c in wc.word_freq.values() if c == 1)
    ttr = (unique_words / wc.total_words) if wc.total_words else 0

    return {
        "frequency": frequency,
        "total_words": wc.total_words,
        "unique_words": unique_words,
        "ttr": ttr,
        "hapax_count": hapax_count,
    }


def frequency_stats(articles: QuerySet) -> FrequencyStats:
    """Backwards-compatible frequency helper using the aggregator."""

    return aggregate_word_stats(articles)["frequency"]


def word_count(articles: QuerySet) -> WordCounter:
    """Backwards-compatible accessor returning the WordCounter object."""

    return WordCounter([article.content for article in articles])


def basic_text_stats(contents) -> dict:
    """Compute lightweight stats: total words, unique words, TTR, hapax count."""

    return aggregate_word_stats([type("obj", (), {"content": c}) for c in contents])


def article_stats(articles: QuerySet) -> dict:
    """Stats helper for a queryset of Article objects."""

    return aggregate_word_stats(articles)


def filter_by_match_type(results: SearchResult, match_type: int) -> SearchResult:
    """
    Filter search results by match type
    1: exact match, 2: partial match
    return only exact matches if match_type is 1
    if match_type is 2 return partial matches only
    """
    filtered_results: SearchResult = {"query": results["query"], "results": []}
    for result in results["results"]:
        if match_type == 1:
            locations = [r for r in result["locations"] if r["type"] == "exact"]
            if locations:
                filtered_results["results"].append(
                    {
                        "article": result["article"],
                        "frequency": len(locations),
                        "locations": locations,
                    }
                )
        elif match_type == 2:
            locations = [r for r in result["locations"] if r["type"] == "partial"]
            if locations:
                filtered_results["results"].append(
                    {
                        "article": result["article"],
                        "frequency": len(locations),
                        "locations": locations,
                    }
                )

    filtered_results["total_frequency"] = sum([r['frequency'] for r in filtered_results["results"]])
    return filtered_results
