from __future__ import annotations

import re
from io import TextIOWrapper

from django.core.files.uploadedfile import UploadedFile
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.db.models import Count
from django.db.models.query import QuerySet
from django.dispatch import receiver
from django.http import HttpResponse
from django.urls import reverse

from main_app.normalize import NameTally, name_key, normalize_name, search_regex
from main_app.types import SearchResult, SearchResultItem
from main_app.utils import (
    clear_corpus_dashboard_cache,
    find_ngrams,
    frequency_stats,
    query_cores,
    search_word,
)


_MALE_NAME_ANNOTATION_RE = re.compile(r"\[(?P<name>[^\[\]]+?)\]")
_FEMALE_NAME_ANNOTATION_RE = re.compile(r"\^\^(?P<name>.+?)\^\^", re.DOTALL)
_TOPONYM_ANNOTATION_RE = re.compile(r"\$\$(?P<name>.+?)\$\$", re.DOTALL)
_ANNOTATION_RE = re.compile(
    r"\[(?P<male>[^\[\]]+?)\]|\^\^(?P<female>.+?)\^\^|\$\$(?P<toponym>.+?)\$\$",
    re.DOTALL,
)
_ANNOTATION_MARKERS = {
    "male": ("[", "]"),
    "female": ("^^", "^^"),
    "toponym": ("$$", "$$"),
}


def _build_plain_projection(text: str) -> tuple[str, list[dict], list[dict]]:
    """Return plain text projection, annotation spans, and visible segment mapping."""

    raw = text or ""
    plain_parts: list[str] = []
    annotations: list[dict] = []
    segments: list[dict] = []
    cursor = 0
    plain_cursor = 0

    for match in _ANNOTATION_RE.finditer(raw):
        if match.start() > cursor:
            segment = raw[cursor : match.start()]
            plain_parts.append(segment)
            seg_len = len(segment)
            segments.append(
                {
                    "raw_start": cursor,
                    "raw_end": match.start(),
                    "plain_start": plain_cursor,
                    "plain_end": plain_cursor + seg_len,
                }
            )
            plain_cursor += seg_len

        if match.group("male") is not None:
            kind = "male"
            opening_len = 1
            closing_len = 1
        elif match.group("female") is not None:
            kind = "female"
            opening_len = 2
            closing_len = 2
        else:
            kind = "toponym"
            opening_len = 2
            closing_len = 2

        inner_raw_start = match.start() + opening_len
        inner_raw_end = match.end() - closing_len
        inner_text = raw[inner_raw_start:inner_raw_end]
        inner_len = len(inner_text)

        plain_parts.append(inner_text)
        segments.append(
            {
                "raw_start": inner_raw_start,
                "raw_end": inner_raw_end,
                "plain_start": plain_cursor,
                "plain_end": plain_cursor + inner_len,
            }
        )

        annotations.append(
            {
                "kind": kind,
                "plain_start": plain_cursor,
                "plain_end": plain_cursor + inner_len,
                "open_raw_start": match.start(),
                "open_raw_end": inner_raw_start,
                "close_raw_start": inner_raw_end,
                "close_raw_end": match.end(),
            }
        )
        plain_cursor += inner_len
        cursor = match.end()

    if cursor < len(raw):
        tail = raw[cursor:]
        tail_len = len(tail)
        plain_parts.append(tail)
        segments.append(
            {
                "raw_start": cursor,
                "raw_end": len(raw),
                "plain_start": plain_cursor,
                "plain_end": plain_cursor + tail_len,
            }
        )

    return "".join(plain_parts), annotations, segments


def _plain_to_raw_index(text: str, plain_index: int) -> int:
    """Map an index from plain projected text to original raw text index."""

    plain_text, _annotations, segments = _build_plain_projection(text)
    idx = max(0, min(plain_index, len(plain_text)))

    for segment in segments:
        if segment["plain_start"] <= idx <= segment["plain_end"]:
            return segment["raw_start"] + (idx - segment["plain_start"])

    return len(text)


def _ranges_intersect(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
    return start_a < end_b and start_b < end_a


def _remove_raw_spans(raw_text: str, spans: list[tuple[int, int]]) -> str:
    text = raw_text
    for start, end in sorted(spans, key=lambda s: s[0], reverse=True):
        text = text[:start] + text[end:]
    return text


def apply_inline_annotation(
    text: str, start: int, end: int, kind: str
) -> tuple[str, bool]:
    """Apply or toggle an annotation marker on a plain-text selection."""

    if kind not in _ANNOTATION_MARKERS:
        return text, False

    plain_text, annotations, _segments = _build_plain_projection(text)
    sel_start = max(0, min(start, end))
    sel_end = min(len(plain_text), max(start, end))

    if sel_start >= sel_end:
        return text, False

    if not plain_text[sel_start:sel_end].strip():
        return text, False

    overlaps = [
        ann
        for ann in annotations
        if _ranges_intersect(
            ann["plain_start"], ann["plain_end"], sel_start, sel_end
        )
    ]
    exact_same_kind = any(
        ann["kind"] == kind
        and ann["plain_start"] == sel_start
        and ann["plain_end"] == sel_end
        for ann in overlaps
    )

    spans_to_remove: list[tuple[int, int]] = []
    for ann in overlaps:
        spans_to_remove.append((ann["open_raw_start"], ann["open_raw_end"]))
        spans_to_remove.append((ann["close_raw_start"], ann["close_raw_end"]))

    new_text = _remove_raw_spans(text, spans_to_remove)

    # Toggle behavior: selecting an already matching annotation removes it.
    if exact_same_kind:
        return new_text, new_text != text

    raw_start = _plain_to_raw_index(new_text, sel_start)
    raw_end = _plain_to_raw_index(new_text, sel_end)
    opening, closing = _ANNOTATION_MARKERS[kind]
    annotated = (
        new_text[:raw_start]
        + opening
        + new_text[raw_start:raw_end]
        + closing
        + new_text[raw_end:]
    )
    return annotated, annotated != text


def resolve_inline_annotation_span(
    text: str,
    selected_text: str,
    approx_start: int | None = None,
    approx_end: int | None = None,
) -> tuple[int, int] | None:
    """Resolve a UI-selected snippet to a plain-text span in article content.

    Matching is whitespace-tolerant to account for browser-rendered text normalization.
    """

    plain_text, _annotations, _segments = _build_plain_projection(text)
    selected = (selected_text or "").strip()
    if not selected:
        return None

    tokens = selected.split()
    if not tokens:
        return None

    # Convert browser-normalized whitespace into a tolerant regex.
    pattern = r"\s+".join(re.escape(token) for token in tokens)
    matches = list(re.finditer(pattern, plain_text))

    # Fallback to exact find if regex route fails.
    if not matches:
        idx = plain_text.find(selected)
        if idx == -1:
            return None
        return idx, idx + len(selected)

    if len(matches) == 1:
        match = matches[0]
        return match.start(), match.end()

    target_start = None
    if isinstance(approx_start, int):
        target_start = approx_start
    elif isinstance(approx_end, int):
        target_start = approx_end

    if target_start is not None:
        best = min(matches, key=lambda m: abs(m.start() - target_start))
        return best.start(), best.end()

    first = matches[0]
    return first.start(), first.end()


class Newspaper(models.Model):
    """
    DB model for storing newspaper info:
    Newspaper:
        - name
        - link to the online source
        - published year
        - issue number
    """

    title = models.CharField(max_length=200, unique=True)
    link = models.URLField(null=True, blank=True)
    published_year = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        default=None,
        validators=[MinValueValidator(1), MaxValueValidator(9999)],
    )
    issue_number = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("newspaper_detail", kwargs={"newspaper_id": self.pk})


class ArticleQuerySet(QuerySet):
    # def search(self, query: str) -> List[SearchResultItem]:
    def search(
        self, query: str, language: int, year: int | str | None = None
    ) -> QuerySet[Article]:
        """
        Search articles for the given query string and return a list of SearchResultItem objects,
        where each SearchResultItem object contains an article that matches the query along with
        the frequency of the query term in that article.

        Args:
            query (str): The search query string.

        Returns:
            List[SearchResultItem]: A list of SearchResultItem objects.
        """
        words = query_cores(query)

        qs = self.filter(language=language)

        if year is not None:
            try:
                year_int = int(year)
                qs = qs.filter(published_year=year_int)
            except (TypeError, ValueError):
                pass

        if not words:
            return qs.none()

        # Coarse prefilter: every query word must appear somewhere in the content.
        # Exact token/phrase matching happens in Python (search_word).
        for word in words:
            qs = qs.filter(content__regex=search_regex(word))
        return qs


class ArticleManager(models.Manager["Article"]):
    def get_queryset(self):
        """
        Return a custom ArticleQuerySet that includes the `search` method.
        """
        return ArticleQuerySet(self.model, using=self._db)

    def search(
        self, query: str, language: int, year: int | str | None = None
    ) -> SearchResult:
        """
        Search articles for the given query string and return a dictionary of search results,
        where the dictionary contains the query string, a list of SearchResultItem objects,
        and the total frequency of the query term across all matching articles.

        Args:
            query (str): The search query string.

        Returns:
            SearchResult: A dictionary of search results.
        """
        query = (query or "").strip()
        if not query:
            return SearchResult(query="", results=[], total_frequency=0)
        queryset = self.get_queryset().search(query, language, year)

        # total_frequency = sum([article.frequency(query) for article in queryset])
        # results = [SearchResultItem(article=article, frequency=article.frequency(query)) for article in queryset]
        # return SearchResult(query=query, results=results, total_frequency=total_frequency)

        # total_frequency = sum([search_word(article.content, query)['count'] for article in queryset])
        # queryset
        total_frequency = 0
        results = []

        for article in queryset:
            search_result = search_word(article.content, query, padding=10)
            if not search_result["frequency"]:
                continue
            results.append(
                SearchResultItem(
                    article=article,
                    frequency=search_result["frequency"],
                    locations=search_result["locations"],
                )
            )
            total_frequency += search_result["frequency"]
        # sort results by exact or partial match
        return SearchResult(
            query=query, results=results, total_frequency=total_frequency
        )

    def ngram_search(
        self,
        query: str,
        language: int,
        year: int | str | None = None,
        before: int = 0,
        after: int = 1,
        match_type: int = 0,
        examples_per_ngram: int = 20,
    ) -> dict:
        """Group every match of `query` with its neighbouring words into n-grams.

        Returns {"query", "total_frequency", "ngrams", "year_totals"}; each n-gram
        is {"left", "keyword", "right", "text", "count", "article_count",
        "examples"} sorted by frequency. `match_type` follows the concordance
        search: 0 both, 1 exact, 2 partial.
        """

        query = (query or "").strip()
        empty = {"query": query, "total_frequency": 0, "ngrams": [], "year_totals": {}}
        if not query:
            return empty

        allowed = {1: {"exact"}, 2: {"partial"}}.get(match_type, {"exact", "partial"})
        groups: dict[tuple, dict] = {}
        year_totals: dict[int, int] = {}
        total = 0

        queryset = self.get_queryset().search(query, language, year)
        for article in queryset.only("id", "title", "content", "published_year"):
            for occ in find_ngrams(article.content, query, before, after):
                if occ["type"] not in allowed:
                    continue
                key = (tuple(occ["left"]), tuple(occ["keyword"]), tuple(occ["right"]))
                group = groups.get(key)
                if group is None:
                    group = groups[key] = {
                        "left": " ".join(occ["left"]),
                        "keyword": " ".join(occ["keyword"]),
                        "right": " ".join(occ["right"]),
                        "text": " ".join(occ["left"] + occ["keyword"] + occ["right"]),
                        "count": 0,
                        "article_ids": set(),
                        "examples": [],
                    }
                group["count"] += 1
                group["article_ids"].add(article.id)
                if len(group["examples"]) < examples_per_ngram:
                    group["examples"].append(
                        {
                            "article_id": article.id,
                            "title": article.title,
                            "year": article.published_year,
                            "context": occ["context"],
                        }
                    )
                year_key = article.published_year or 0
                year_totals[year_key] = year_totals.get(year_key, 0) + 1
                total += 1

        ngrams = []
        for group in groups.values():
            group["article_count"] = len(group.pop("article_ids"))
            ngrams.append(group)
        ngrams.sort(key=lambda g: (-g["count"], g["text"]))

        return {
            "query": query,
            "total_frequency": total,
            "ngrams": ngrams,
            "year_totals": year_totals,
        }

    def create_from_csv(self, csv_file: UploadedFile):
        """
        Create articles from csv file
        """
        # read csv file
        import csv

        # Use a TextIOWrapper to handle newlines within cells
        wrapper = TextIOWrapper(csv_file, encoding="utf-8-sig")
        csv_data = csv.DictReader(wrapper, delimiter=",")

        articles = []
        for row in csv_data:
            # print(row,"\n")
            try:
                newspaper, _ = Newspaper.objects.get_or_create(title=row["newspaper"])
                raw_year = row.get("published_year")
                try:
                    published_year = int(raw_year) if raw_year not in ("", None) else None
                except (TypeError, ValueError):
                    published_year = None

                articles.append(
                    Article(
                        title=row["title"],
                        author=row["author"],
                        newspaper=newspaper,
                        content=row["content"],
                        published_year=published_year,
                        language=1 if row["language"].capitalize() == "English" else 2,
                        # issue_number=row["issue_number"],
                    )
                )
            except Exception as e:
                print(row)
                print(e)
                return []
        created = Article.objects.bulk_create(articles)
        clear_corpus_dashboard_cache()
        return created

    def to_csv(self) -> HttpResponse:
        """
        Return csv file of all articles
        """
        import csv

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="articles.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "title",
                "author",
                "newspaper",
                "content",
                "published_year",
                "language",
                "issue_number",
            ]
        )
        for article in self.all():
            writer.writerow(
                [
                    article.title,
                    article.author,
                    article.newspaper.title,
                    article.content,
                    article.published_year,
                    article.language,
                    article.newspaper.issue_number,
                ]
            )
        return response

    def create_frequency_csv(self, language) -> HttpResponse:
        """
        Create frequency csv file
        """
        import csv

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="frequency.csv"'
        writer = csv.writer(response)
        writer.writerow(["frequency", "word"])
        frequency = frequency_stats(self.filter(language=language))
        # for article in self.all():
        #     for word in article.content.split():
        #         writer.writerow([word, article.frequency(word)])
        for stat in frequency:
            writer.writerow([stat["count"], stat["word"]])
        return response

    def total_name_counts(self) -> dict[str, int]:
        """Aggregate annotated male/female name and toponym counts across all articles."""

        male = 0
        female = 0
        toponym = 0
        for article in self.all():
            counts = article.annotated_name_counts()
            male += counts.get("male", 0)
            female += counts.get("female", 0)
            toponym += counts.get("toponym", 0)

        return {
            "male": male,
            "female": female,
            "toponym": toponym,
            "total": male + female,
            "total_with_toponym": male + female + toponym,
        }

    def annotated_name_stats(
        self,
        articles: QuerySet["Article"] | None = None,
        include_toponyms: bool = False,
    ) -> dict:
        """Aggregate annotated name counts and frequency for given articles (defaults to all)."""

        articles = articles if articles is not None else self.all()

        kinds = ("male", "female", "toponym") if include_toponyms else ("male", "female")
        tally = NameTally()

        if isinstance(articles, QuerySet):
            article_iter = articles.only("content").iterator(chunk_size=500)
        else:
            article_iter = articles

        for article in article_iter:
            names = article.annotated_names()
            for kind in kinds:
                for name in names[kind]:
                    tally.add(kind, name)

        counts = {"male": 0, "female": 0, "toponym": 0}
        for (kind, _key), count in tally.counts.items():
            counts[kind] += count
        frequency = tally.frequency()

        counts["total"] = counts["male"] + counts["female"]
        if include_toponyms:
            counts["total_with_toponym"] = (
                counts["male"] + counts["female"] + counts["toponym"]
            )

        return {"counts": counts, "frequency": frequency}

    def random3(self):
        """
        Return 3 random articles
        """
        return self.order_by("?")[:3]

    def year_list(self):
        """
        Return a list of years with counts
        """
        return (
            self.values("published_year")
            .annotate(count=Count("published_year"))
            .order_by("-published_year")
        )


class Article(models.Model):
    """
    DB model for storing article info:
    Article:
        - title
        - author
        - newspaper name
        - text content max of 505 words, min 495
    """

    class Language(models.IntegerChoices):
        ENGLISH = 1, "English"
        UZBEK = 2, "Uzbek"

    ENGLISH = Language.ENGLISH
    UZBEK = Language.UZBEK

    title = models.CharField(max_length=500)
    author = models.CharField(max_length=200, null=True, blank=True)
    newspaper = models.ForeignKey(Newspaper, on_delete=models.CASCADE)
    content = models.TextField()
    language = models.PositiveSmallIntegerField(
        choices=Language.choices, default=Language.UZBEK
    )
    published_year = models.PositiveSmallIntegerField(
        null=True,
        default=None,
        validators=[MinValueValidator(1), MaxValueValidator(9999)],
    )
    link = models.URLField(null=True, blank=True, default=None)

    objects = ArticleManager()

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("article_detail", kwargs={"article_id": self.pk})

    def frequency(self, word: str):
        """
        Get word frequency of the article
        """
        return self.content.lower().count(word.lower())

    def annotated_names(self, *, normalize: bool = False) -> dict[str, list[str]]:
        """Extract annotated entities from article content.

        - Male names: `[Mr. Smith]` (square brackets)
        - Female names: `^^Olivera Anna^^` (double carets)
        - Toponyms: `$$Tashkent$$` (double dollar signs)

        Returns occurrences (not de-duplicated). With ``normalize=True`` names
        get unified apostrophes, Latin look-alikes and whitespace; stored text is
        never rewritten.
        """

        text = self.content or ""

        male = [m.group("name").strip() for m in _MALE_NAME_ANNOTATION_RE.finditer(text)]
        female = [m.group("name").strip() for m in _FEMALE_NAME_ANNOTATION_RE.finditer(text)]
        toponym = [m.group("name").strip() for m in _TOPONYM_ANNOTATION_RE.finditer(text)]

        male = [n for n in male if n]
        female = [n for n in female if n]
        toponym = [n for n in toponym if n]

        names = {"male": male, "female": female, "toponym": toponym}
        if normalize:
            return {
                kind: [normalize_name(name) for name in occurrences]
                for kind, occurrences in names.items()
            }
        return names

    def annotated_name_counts(self) -> dict[str, int]:
        """Return total counts of annotated male/female names and toponyms."""

        names = self.annotated_names()
        return {
            "male": len(names["male"]),
            "female": len(names["female"]),
            "toponym": len(names["toponym"]),
        }

    def annotated_unique_name_counts(self) -> dict[str, int]:
        """Return unique counts of annotated male/female names and toponyms."""

        names = self.annotated_names()
        return {
            kind: len({name_key(name) for name in occurrences if name_key(name)})
            for kind, occurrences in names.items()
        }

    def apply_annotation(self, start: int, end: int, kind: str) -> bool:
        """Apply or toggle an inline annotation marker and persist article content."""

        updated_content, changed = apply_inline_annotation(self.content or "", start, end, kind)
        if not changed:
            return False

        self.content = updated_content
        self.save(update_fields=["content"])
        return True

    class Meta:
        ordering = ["-published_year", "newspaper"]


@receiver([post_save, post_delete], sender=Article)
def clear_article_dashboard_cache(**kwargs) -> None:
    clear_corpus_dashboard_cache()


def create_frequency_csv(articles: QuerySet[Article], filename="frequency.csv"):
    import csv

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(["frequency", "word"])
    frequency = frequency_stats(articles)
    for stat in frequency:
        writer.writerow([stat["count"], stat["word"]])
    return response
