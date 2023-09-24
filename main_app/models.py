from io import TextIOWrapper
from typing import List
from django.db import models
from django.http import HttpResponse
from main_app.types import SearchResult, SearchResultItem
from main_app.utils import RegexpReplace, frequency_stats, search_word
from django.core.files.uploadedfile import UploadedFile

from main_app.validators import max_word_count, min_word_count
from django.db.models import Count
from django.db.models.query import QuerySet
from django.db.models import Func, IntegerField
from django.db.models.functions import Replace
from django.db.models import Count, Q, Sum, F


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
    published_year = models.DateField(blank=True, null=True, default=None)
    issue_number = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.title


class ArticleQuerySet(QuerySet):
    # def search(self, query: str) -> List[SearchResultItem]:
    def search(self, query: str, language: int, year: str | None = None) -> QuerySet:
        """
        Search articles for the given query string and return a list of SearchResultItem objects,
        where each SearchResultItem object contains an article that matches the query along with
        the frequency of the query term in that article.

        Args:
            query (str): The search query string.

        Returns:
            List[SearchResultItem]: A list of SearchResultItem objects.
        """
        # queryset = self.filter(content__icontains=query)
        # return [SearchResultItem(article=article, frequency=article.frequency(query)) for article in queryset]
        if year is None:
            return self.filter(content__icontains=query, language=language)
        return self.filter(content__icontains=query, language=language, published_year__year=year)


class ArticleManager(models.Manager):
    def get_queryset(self):
        """
        Return a custom ArticleQuerySet that includes the `search` method.
        """
        return ArticleQuerySet(self.model, using=self._db)

    def search(self, query: str, language: int, year: str | None = None) -> SearchResult:
        """
        Search articles for the given query string and return a dictionary of search results,
        where the dictionary contains the query string, a list of SearchResultItem objects,
        and the total frequency of the query term across all matching articles.

        Args:
            query (str): The search query string.

        Returns:
            SearchResult: A dictionary of search results.
        """
        query = query.strip()
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
            results.append(
                SearchResultItem(
                    article=article, frequency=search_result["frequency"], locations=search_result["locations"]
                )
            )
            total_frequency += search_result["frequency"]
        # sort results by exact or partial match
        return SearchResult(query=query, results=results, total_frequency=total_frequency)

    # def create_from_csv(self, csv_file):
    #     """
    #     Create articles from csv file
    #     """
    #     # read csv file
    #     import csv

    #     # print(csv_file)
    #     reader = csv.DictReader(csv_file)
    #     articles = []
    #     # create articles
    #     # print(reader[0])
    #     # print(reader[1])
    #     for row in reader:
    #         # print(row)
    #         try:
    #             # newspaper, _ = Newspaper.objects.get_or_create(name=row["newspaper"], published_year=f"{row['published_year']}-01-01")
    #             newspaper, _ = Newspaper.objects.get_or_create(title=row["newspaper"], published_year=f"2023-01-01")
    #             articles.append(
    #                 Article(
    #                     title=row["title"],
    #                     author=row["author"],
    #                     newspaper=newspaper,
    #                     content=row["content"],
    #                     published_year=f"{row['published_year']}-01-01",
    #                     language=1 if row["language"].capitalize() == "English" else 2,
    #                     # issue_number=row["issue_number"],
    #                 )
    #             )
    #         except Exception as e:
    #             print(row)
    #             print(e)
    #             return []
    #     return Article.objects.bulk_create(articles)

    def create_from_csv(self, csv_file: UploadedFile):
        """
        Create articles from csv file
        """
        # read csv file
        import csv
        # Use a TextIOWrapper to handle newlines within cells
        wrapper = TextIOWrapper(csv_file, encoding='utf-8-sig')
        csv_data = csv.DictReader(wrapper, delimiter=",")
        
        articles = []
        for row in csv_data:
            # print(row,"\n")
            try:
                newspaper, _ = Newspaper.objects.get_or_create(title=row["newspaper"])
                articles.append(
                    Article(
                        title=row["title"],
                        author=row["author"],
                        newspaper=newspaper,
                        content=row["content"],
                        published_year=f"{row['published_year']}-01-01",
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
        writer.writerow(["title", "author", "newspaper", "content", "published_year", "language", "issue_number"])
        for article in self.all():
            writer.writerow(
                [
                    article.title,
                    article.author,
                    article.newspaper.title,
                    article.content,
                    article.published_year,
                    article.language,
                    article.issue_number,
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

    def random3(self):
        """
        Return 3 random newspapers
        """
        return self.order_by("?")[:4]

    def year_list(self):
        """
        Return 3 random newspapers
        """
        return self.values("published_year").annotate(count=Count("published_year")).order_by("-published_year")


class Article(models.Model):
    """
    DB model for storing article info:
    Article:
        - title
        - author
        - newspaper name
        - text content max of 505 words, min 495
    """

    ENGLISH = 1
    UZBEK = 2

    title = models.CharField(max_length=500)
    author = models.CharField(max_length=200, null=True, blank=True)
    newspaper = models.ForeignKey(Newspaper, on_delete=models.CASCADE)
    content = models.TextField()
    language = models.PositiveSmallIntegerField(choices=((ENGLISH, "English"), (UZBEK, "Uzbek")), default=UZBEK)
    published_year = models.DateField(null=True, default=None)
    issue_number = models.IntegerField(null=True, blank=True, default=None)
    
    word_count_total = models.IntegerField(null=True, blank=True, default=None)
    word_count_unique = models.IntegerField(null=True, blank=True, default=None)
    
    objects = ArticleManager()

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Calculate word_count_total
        self.word_count_total = len(self.content.split())

        # Calculate word_count_unique
        unique_words = set(self.content.split())
        self.word_count_unique = len(unique_words)

        super(Article, self).save(*args, **kwargs)

    def frequency(self, word: str):
        """
        Get word frequency of the article
        """
        return self.content.lower().count(word.lower())
        # freq = get_word_frequency(word, self.content)
        # return freq

    class Meta:
        ordering = ["-published_year", "newspaper"]


# class ArticleWordFrequency(models.Model):
#     """
#     DB model for storing article word frequency info:
#     ArticleWordFrequency:
#         - article
#         - word
#         - frequency
#     """

#     article = models.ForeignKey(Article, on_delete=models.CASCADE)
#     word = models.CharField(max_length=100)
#     frequency = models.IntegerField()

#     def __str__(self):
#         return self.word

#     class Meta:
#         unique_together = ('article', 'word', 'frequency')


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
