from typing import List
from django.db import models
from main_app.types import SearchResult, SearchResultItem
from main_app.utils import RegexpReplace, search_word

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

    name = models.CharField(max_length=100)
    link = models.URLField(null=True, blank=True)
    published_year = models.DateField()
    issue_number = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.name


class ArticleQuerySet(QuerySet):
    # def search(self, query: str) -> List[SearchResultItem]:
    def search(self, query: str) -> QuerySet:
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
        return self.filter(content__icontains=query)


class ArticleManager(models.Manager):
    def get_queryset(self):
        """
        Return a custom ArticleQuerySet that includes the `search` method.
        """
        return ArticleQuerySet(self.model, using=self._db)

    def search(self, query: str) -> SearchResult:
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
        queryset = self.get_queryset().search(query)

        # total_frequency = sum([article.frequency(query) for article in queryset])
        # results = [SearchResultItem(article=article, frequency=article.frequency(query)) for article in queryset]
        # return SearchResult(query=query, results=results, total_frequency=total_frequency)
        
        # total_frequency = sum([search_word(article.content, query)['count'] for article in queryset])
        # queryset
        total_frequency = 0
        results = []

        for article in queryset:
            search_result = search_word(article.content, query, padding=10)
            results.append(SearchResultItem(article=article, frequency=search_result['frequency'], locations=search_result['locations']))
            total_frequency += search_result['frequency']
        # sort results by exact or partial match
        return SearchResult(query=query, results=results, total_frequency=total_frequency)



class Article(models.Model):
    """
    DB model for storing article info:
    Article:
        - title
        - author
        - newspaper name
        - text content max of 505 words, min 495
    """

    title = models.CharField(max_length=100)
    author = models.CharField(max_length=100, null=True, blank=True)
    newspaper = models.ForeignKey(Newspaper, on_delete=models.CASCADE)
    content = models.TextField()
    language = models.PositiveSmallIntegerField(choices=((1, 'English'), (2, 'Uzbek')), default=2)

    objects = ArticleManager()
    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        max_word_count(self.content, 600)
        min_word_count(self.content, 300)
    
    def frequency(self, word:str):
        """
        Get word frequency of the article
        """
        return self.content.lower().count(word.lower())
        # freq = get_word_frequency(word, self.content)
        # return freq








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



