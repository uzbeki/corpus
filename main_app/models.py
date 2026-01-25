from __future__ import annotations

import re
from io import TextIOWrapper

from django.core.files.uploadedfile import UploadedFile
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Count
from django.db.models.query import QuerySet
from django.http import HttpResponse
from django.urls import reverse

from main_app.types import SearchResult, SearchResultItem
from main_app.utils import frequency_stats, search_word


_MALE_NAME_ANNOTATION_RE = re.compile(r"\[(?P<name>[^\[\]]+?)\]")
_FEMALE_NAME_ANNOTATION_RE = re.compile(r"\^\^(?P<name>.+?)\^\^", re.DOTALL)
_APOSTROPHE_VARIANTS = ("'", "’", "ʼ", "‘", "′", "`")


def _normalize_apostrophes(value: str) -> str:
    """Normalize all apostrophe-like characters to a plain ASCII apostrophe."""

    normalized = value
    for ch in _APOSTROPHE_VARIANTS[1:]:  # skip the plain apostrophe at index 0
        normalized = normalized.replace(ch, "'")
    return normalized


def _query_variants(query: str) -> set[str]:
    """Return a set of query variants covering common apostrophe glyphs."""

    if not query:
        return set()

    variants: set[str] = set()
    # Start with normalized version
    base = _normalize_apostrophes(query)
    variants.add(base)
    variants.add(query)

    # Generate variants by swapping apostrophe glyphs
    for src in _APOSTROPHE_VARIANTS:
        if src not in query:
            continue
        for dst in _APOSTROPHE_VARIANTS:
            if src == dst:
                continue
            variants.add(query.replace(src, dst))

    return {v for v in variants if v}


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
        query = (query or "").strip()
        variants = _query_variants(query)

        qs = self.filter(language=language)

        if year is not None:
            try:
                year_int = int(year)
                qs = qs.filter(published_year=year_int)
            except (TypeError, ValueError):
                pass

        if not variants:
            return qs.none()

        from django.db.models import Q

        q_obj = Q()
        for v in variants:
            q_obj |= Q(content__icontains=v)

        return qs.filter(q_obj)


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
            search_result = search_word(article.content, _normalize_apostrophes(query), padding=10)
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
        return Article.objects.bulk_create(articles)

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
        """Aggregate annotated male/female name counts across all articles."""

        male = 0
        female = 0
        for article in self.all():
            counts = article.annotated_name_counts()
            male += counts.get("male", 0)
            female += counts.get("female", 0)

        return {"male": male, "female": female, "total": male + female}

    def annotated_name_stats(self, articles: QuerySet["Article"] | None = None) -> dict:
        """Aggregate annotated name counts and frequency for given articles (defaults to all)."""

        articles = articles if articles is not None else self.all()

        counts = {"male": 0, "female": 0}
        freq: dict[tuple[str, str], int] = {}

        for article in articles:
            names = article.annotated_names()
            for n in names["male"]:
                counts["male"] += 1
                freq[("male", n)] = freq.get(("male", n), 0) + 1
            for n in names["female"]:
                counts["female"] += 1
                freq[("female", n)] = freq.get(("female", n), 0) + 1

        frequency = [
            {"name": name, "gender": gender, "count": count}
            for (gender, name), count in freq.items()
        ]
        frequency.sort(key=lambda x: (-x["count"], x["name"]))

        counts["total"] = counts["male"] + counts["female"]

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

    def annotated_names(self) -> dict[str, list[str]]:
        """Extract annotated names from article content.

        - Male names: `[Mr. Smith]` (square brackets)
        - Female names: `^^Olivera Anna^^` (double carets)

        Returns raw occurrences (not de-duplicated).
        """

        text = self.content or ""

        male = [m.group("name").strip() for m in _MALE_NAME_ANNOTATION_RE.finditer(text)]
        female = [m.group("name").strip() for m in _FEMALE_NAME_ANNOTATION_RE.finditer(text)]

        male = [n for n in male if n]
        female = [n for n in female if n]

        return {"male": male, "female": female}

    def annotated_name_counts(self) -> dict[str, int]:
        """Return total counts of annotated male/female names."""

        names = self.annotated_names()
        return {"male": len(names["male"]), "female": len(names["female"])}

    def annotated_unique_name_counts(self) -> dict[str, int]:
        """Return unique counts of annotated male/female names."""

        names = self.annotated_names()
        return {
            "male": len(set(names["male"])),
            "female": len(set(names["female"])),
        }

    class Meta:
        ordering = ["-published_year", "newspaper"]


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
