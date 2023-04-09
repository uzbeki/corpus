from django.db import models

from main_app.validators import max_word_count, min_word_count


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

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        max_word_count(self.content, 505)
        min_word_count(self.content, 495)



class ArticleWordFrequency(models.Model):
    """
    DB model for storing article word frequency info:
    ArticleWordFrequency:
        - article
        - word
        - frequency
    """

    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    word = models.CharField(max_length=100)
    frequency = models.IntegerField()

    def __str__(self):
        return self.word

    class Meta:
        unique_together = ('article', 'word', 'frequency')