from django.test import TestCase

from main_app.models import Article, Newspaper
from main_app.counter import WordCounter


class ArticleAnnotationParsingTests(TestCase):
    def test_annotated_name_counts(self):
        newspaper = Newspaper.objects.create(title="Test Newspaper")
        article = Article.objects.create(
            title="T",
            newspaper=newspaper,
            content=(
                "Hello [Mr. Smith]. "
                "And ^^Olivera Anna^^ met [John Doe]. "
                "Again ^^Olivera Anna^^."
            ),
            language=Article.ENGLISH,
        )

        self.assertEqual(article.annotated_name_counts(), {"male": 2, "female": 2})
        self.assertEqual(
            article.annotated_unique_name_counts(), {"male": 2, "female": 1}
        )

    def test_annotated_names_strips_and_ignores_empty(self):
        newspaper = Newspaper.objects.create(title="Test Newspaper 2")
        article = Article(
            title="T2",
            newspaper=newspaper,
            content="[] ^^   ^^ [  Mr. X  ]",
            language=Article.ENGLISH,
        )

        self.assertEqual(article.annotated_names(), {"male": ["Mr. X"], "female": []})

class SearchApostropheTests(TestCase):
    def setUp(self):
        self.paper = Newspaper.objects.create(title="Test Paper")

    def test_search_matches_ascii_apostrophe(self):
        Article.objects.create(
            title="Uzbek sample",
            newspaper=self.paper,
            content="Bu xo'jalik haqida maqola.",
            language=Article.UZBEK,
            published_year="2020-01-01",
        )

        results = Article.objects.search("xo'jalik", language=Article.UZBEK)
        self.assertEqual(len(results["results"]), 1)
        self.assertEqual(results["total_frequency"], 1)

    def test_search_matches_curly_apostrophe_in_text(self):
        Article.objects.create(
            title="Curly apostrophe",
            newspaper=self.paper,
            content="Bu xo’jalik haqida maqola.",
            language=Article.UZBEK,
            published_year="2021-01-01",
        )

        results = Article.objects.search("xo'jalik", language=Article.UZBEK)
        self.assertEqual(len(results["results"]), 1)
        self.assertEqual(results["total_frequency"], 1)


class WordCounterApostropheTests(TestCase):
    def test_counts_uzbek_apostrophe_variants(self):
        wc = WordCounter([
            "xo'jalik xo’jalik cho'l cho’l",
        ])

        self.assertEqual(wc.word_freq.get("xo'jalik"), 2)
        self.assertEqual(wc.word_freq.get("cho'l"), 2)
