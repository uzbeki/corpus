import nltk
import string
from django.db.models import Func, Count, QuerySet
from nltk.tokenize import RegexpTokenizer
from main_app.counter import WordCounter
from main_app.types import Context, FrequencyStats, SearchResult, SearchResultItem

nltk.download("punkt")


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
    """

    exaple RegexpReplace(
        'content',
        fr'((\S+\s+){{0,5}}\S*{substring}\S*(\s+\S+){{0,5}})',
        r'<mark>\1</mark>',
        'gi'  # 'gi' for case-insensitive matching
    )
    """

    function = "REGEXP_REPLACE"  # The name of the function in the database
    arity = 2  # The number of arguments the function takes


from nltk.tokenize import word_tokenize
from django.utils.html import strip_tags


_APOSTROPHE_TRANSLATION = str.maketrans({"’": "'", "ʼ": "'", "‘": "'", "′": "'", "`": "'"})


def search_word(text: str, word: str, padding=5) -> SearchResultItem:
    # Normalize apostrophes so `xo'jalik` matches text with `xo’jalik`.
    word = (word or "").translate(_APOSTROPHE_TRANSLATION).lower()
    text = strip_tags(text or "").translate(_APOSTROPHE_TRANSLATION)  # remove HTML tags and normalize
    tokens = word_tokenize(text)
    count = 0
    results = {"article": None, "frequency": 0, "locations": []}  # type: ignore
    for i, token in enumerate(tokens):
        exact_match = token.lower() == word
        partial_match = word in token.lower()
        if exact_match or partial_match:
            count += 1
            start = max(0, i - padding)
            end = min(len(tokens), i + padding + 1)
            context = " ".join(tokens[start:end])
            # results['locations'].append((count, context, "exact" if exact_match else "partial"))
            results["locations"].append(
                Context(
                    count=count,
                    context=context,
                    type="exact" if exact_match else "partial",
                )
            )
    results["frequency"] = count

    # sort locations that exact matches come first
    results["locations"].sort(key=lambda x: x["type"], reverse=False)
    return results


# class FrequencyStat(TypedDict):
#     word: str
#     count: int
#     language: str

# FrequencyStats= list[FrequencyStat]


def aggregate_word_stats(articles: QuerySet) -> dict:
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

    wc = WordCounter([article.content for article in articles])

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
