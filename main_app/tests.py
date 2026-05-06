from django.core.cache import cache
from django.test import TestCase

from main_app.models import Article, Newspaper
from main_app.counter import WordCounter
from main_app.utils import CORPUS_DASHBOARD_CACHE_KEY


class ArticleAnnotationParsingTests(TestCase):
    def test_annotated_name_counts(self):
        newspaper = Newspaper.objects.create(title="Test Newspaper")
        article = Article.objects.create(
            title="T",
            newspaper=newspaper,
            content=(
                "Hello [Mr. Smith]. "
                "And ^^Olivera Anna^^ met [John Doe]. "
                "Again ^^Olivera Anna^^ in $$Tashkent$$."
            ),
            language=Article.ENGLISH,
        )

        self.assertEqual(
            article.annotated_name_counts(),
            {"male": 2, "female": 2, "toponym": 1},
        )
        self.assertEqual(
            article.annotated_unique_name_counts(),
            {"male": 2, "female": 1, "toponym": 1},
        )

    def test_annotated_names_strips_and_ignores_empty(self):
        newspaper = Newspaper.objects.create(title="Test Newspaper 2")
        article = Article(
            title="T2",
            newspaper=newspaper,
            content="[] ^^   ^^ [  Mr. X  ]",
            language=Article.ENGLISH,
        )

        self.assertEqual(
            article.annotated_names(),
            {"male": ["Mr. X"], "female": [], "toponym": []},
        )


class DashboardPayloadTests(TestCase):
    def setUp(self):
        cache.clear()
        self.paper = Newspaper.objects.create(title="Dashboard Paper")

    def test_word_frequency_data_includes_summary_stats(self):
        Article.objects.create(
            title="English",
            newspaper=self.paper,
            content="Alpha beta [John] ^^Jane^^ $$Paris$$ alpha",
            language=Article.ENGLISH,
            published_year=2020,
        )
        Article.objects.create(
            title="Uzbek",
            newspaper=self.paper,
            content="salom dunyo [Ali] $$Toshkent$$",
            language=Article.UZBEK,
            published_year=2021,
        )

        response = self.client.get("/word_frequency_data")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["article_count"], 2)
        self.assertEqual(payload["summary"]["word_count"], 10)
        self.assertEqual(payload["summary"]["name_counts"]["male"], 2)
        self.assertEqual(payload["summary"]["name_counts"]["female"], 1)
        self.assertEqual(payload["summary"]["name_counts"]["toponym"], 2)
        self.assertEqual(payload["summary"]["name_counts"]["total"], 3)
        self.assertEqual(payload["summary"]["text_stats"]["hapax_count"], 8)
        self.assertAlmostEqual(payload["summary"]["text_stats"]["ttr"], 0.9)

    def test_article_save_clears_dashboard_cache(self):
        article = Article.objects.create(
            title="Cached",
            newspaper=self.paper,
            content="one two",
            language=Article.ENGLISH,
            published_year=2020,
        )
        cache.set(CORPUS_DASHBOARD_CACHE_KEY, {"stale": True})

        article.content = "one two three"
        article.save(update_fields=["content"])

        self.assertIsNone(cache.get(CORPUS_DASHBOARD_CACHE_KEY))

class SearchApostropheTests(TestCase):
    def setUp(self):
        self.paper = Newspaper.objects.create(title="Test Paper")

    def test_search_matches_ascii_apostrophe(self):
        Article.objects.create(
            title="Uzbek sample",
            newspaper=self.paper,
            content="Bu xo'jalik haqida maqola.",
            language=Article.UZBEK,
            published_year=2020,
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
            published_year=2021,
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
