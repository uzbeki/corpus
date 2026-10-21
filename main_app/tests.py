import csv
import io
from unittest.mock import call, patch

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase

from main_app.models import Article, Newspaper
from main_app.counter import WordCounter, cleanse_word
from main_app import utils
from main_app.normalize import NameTally, normalize_name
from main_app.utils import CORPUS_DASHBOARD_CACHE_KEY, find_ngrams, search_word


class PunktResourceTests(SimpleTestCase):
    def tearDown(self):
        utils._PUNKT_READY = False

    @patch("main_app.utils.nltk.download")
    @patch("main_app.utils.nltk.data.find")
    def test_ensure_punkt_downloads_all_missing_resources(self, find, download):
        utils._PUNKT_READY = False
        find.side_effect = LookupError

        utils.ensure_punkt()

        self.assertEqual(
            find.call_args_list,
            [
                call("tokenizers/punkt"),
                call("tokenizers/punkt_tab/english"),
            ],
        )
        self.assertEqual(
            download.call_args_list,
            [
                call("punkt", quiet=True, raise_on_error=True),
                call("punkt_tab", quiet=True, raise_on_error=True),
            ],
        )


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


class AnnotationApostropheTests(TestCase):
    def setUp(self):
        cache.clear()
        self.paper = Newspaper.objects.create(title="Apostrophe Paper")
        self.variants = ["O'zbekiston", "Oʻzbekiston", "O‘zbekiston", "O’zbekiston",
                         "Oʼzbekiston", "O′zbekiston", "O`zbekiston"]
        self.content = " ".join(f"$${name}$$" for name in self.variants)
        self.article = Article.objects.create(
            title="Variants", newspaper=self.paper, language=Article.UZBEK,
            content=self.content + " $$Oʻzbekiston Respublikasi$$ [Gʻani] [G‘ani]",
        )
        Article.objects.create(
            title="Another article", newspaper=self.paper, language=Article.UZBEK,
            content="$$O‘zbekiston$$",
        )

    def test_statistics_merge_variants_without_rewriting_source(self):
        stats = Article.objects.annotated_name_stats(include_toponyms=True)
        self.assertIn(
            {"name": "O'zbekiston", "gender": "toponym", "count": 8},
            stats["frequency"],
        )
        self.assertIn(
            {"name": "O'zbekiston Respublikasi", "gender": "toponym", "count": 1},
            stats["frequency"],
        )
        self.assertIn(
            {"name": "G'ani", "gender": "male", "count": 2}, stats["frequency"],
        )
        self.assertEqual(len(stats["frequency"]), 3)
        self.assertEqual(stats["counts"]["toponym"], 9)
        self.assertEqual(self.article.annotated_unique_name_counts()["toponym"], 2)
        self.article.refresh_from_db()
        self.assertEqual(self.article.content,
                         self.content + " $$Oʻzbekiston Respublikasi$$ [Gʻani] [G‘ani]")
        self.assertEqual(self.article.annotated_names()["toponym"][:7], self.variants)

    def test_dashboard_article_and_csv_agree(self):
        expected = [
            {"name": "O'zbekiston", "gender": "toponym", "count": 8},
            {"name": "O'zbekiston Respublikasi", "gender": "toponym", "count": 1},
        ]
        response = self.client.get("/word_frequency_data")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["uzbek"]["toponyms"]["frequency"], expected)
        # Repeated requests must serve the same normalized cached data.
        self.assertEqual(self.client.get("/word_frequency_data").json(), response.json())
        article_response = self.client.get(f"/article/{self.article.pk}/frequency_data")
        self.assertEqual(article_response.json()["toponyms"]["frequency"][0]["count"], 7)
        response = self.client.get("/word_frequency_data", {
            "full": "1", "language": "uzbek", "dataset": "toponyms",
        })
        self.assertEqual(list(csv.reader(io.StringIO(response.content.decode()))), [
            ["toponym", "count"], ["O'zbekiston", "8"],
            ["O'zbekiston Respublikasi", "1"],
        ])


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
            "xo'jalik xo’jalik cho'l cho’l Oʻzbekiston O‘zbekiston",
        ])

        self.assertEqual(wc.word_freq.get("xo'jalik"), 2)
        self.assertEqual(wc.word_freq.get("cho'l"), 2)
        self.assertEqual(wc.word_freq.get("o'zbekiston"), 2)


class NameNormalizationTests(SimpleTestCase):
    def test_merges_glyph_case_and_spacing_variants(self):
        tally = NameTally()
        for name in [
            "O'zbekiston", "Oʻzbekiston", "O‘zbekiston",
            "\u041e'zbekiston",  # Cyrillic capital O
            "O'ZBEKISTON", "O'zbekiston,", "O\u00ad'zbekiston",
            "Toshkent  shahri", "Toshkent\nshahri",
        ]:
            tally.add("toponym", name)

        self.assertEqual(tally.frequency(), [
            {"name": "O'zbekiston", "gender": "toponym", "count": 7},
            {"name": "Toshkent shahri", "gender": "toponym", "count": 2},
        ])

    def test_pure_cyrillic_names_are_not_transliterated(self):
        self.assertEqual(normalize_name("Москва"), "Москва")

    def test_word_cleaning_folds_mixed_script_letters(self):
        # Cyrillic "А" inside a Latin word used to be dropped, leaving "mmo".
        self.assertEqual(cleanse_word("\u0410mmo,"), "ammo")
        self.assertEqual(cleanse_word("O`zbekiston"), "o'zbekiston")


class SearchMatchingTests(SimpleTestCase):
    def test_apostrophe_words_match_exactly(self):
        # NLTK tokenised ko'p as ko / ' / p, so exact matches were missed.
        result = search_word("Bu ko'p yaxshi. Juda koʻp!", "ko'p")
        self.assertEqual(result["frequency"], 2)
        self.assertEqual({loc["type"] for loc in result["locations"]}, {"exact"})

    def test_multi_word_annotated_phrase(self):
        text = "U $$Toshkent shahri$$ markazida. [KPSS Markaziy Komiteti] qarori."
        self.assertEqual(search_word(text, "Toshkent shahri")["frequency"], 1)
        result = search_word(text, "KPSS Markaziy Komiteti")
        self.assertEqual(result["frequency"], 1)
        self.assertEqual(result["locations"][0]["type"], "exact")

    def test_glued_punctuation_and_hyphen_compounds(self):
        text = "Biz bag'ishladik.$$Toshkent$$ va xotin-qizlar, yetmay,nopoklik"
        self.assertEqual(search_word(text, "Toshkent")["frequency"], 1)
        self.assertEqual(search_word(text, "nopoklik")["frequency"], 1)
        # Word statistics store compounds without the hyphen; both spellings must match.
        self.assertEqual(search_word(text, "xotinqizlar")["frequency"], 1)
        self.assertEqual(search_word(text, "xotin-qizlar")["frequency"], 1)
        self.assertEqual(
            WordCounter([text]).word_freq,
            {"biz": 1, "bag'ishladik": 1, "toshkent": 1, "va": 1, "xotinqizlar": 1,
             "yetmay": 1, "nopoklik": 1},
        )
        self.assertEqual(WordCounter(["narxi 3.5 yoki 1,200 so'm"]).word_freq["35"], 1)

    def test_partial_match(self):
        result = search_word("kitob kitoblarga kitobxon", "kitob")
        self.assertEqual(
            sorted(loc["type"] for loc in result["locations"]),
            ["exact", "partial", "partial"],
        )


class NgramTests(SimpleTestCase):
    def test_window_and_sentence_boundaries(self):
        text = "Men kitob o'qidim. Yangi kitoblarga ko'p pul. Bu kitob."
        ngrams = find_ngrams(text, "kitob", before=1, after=2)
        self.assertEqual(
            [(n["left"], n["keyword"], n["right"], n["type"]) for n in ngrams],
            [
                (["men"], ["kitob"], ["o'qidim"], "exact"),
                (["yangi"], ["kitoblarga"], ["ko'p", "pul"], "partial"),
                (["bu"], ["kitob"], [], "exact"),
            ],
        )

    def test_display_keeps_hyphens(self):
        ngrams = find_ngrams("Faol xotin-qizlar uchun", "xotinqizlar", before=1, after=1)
        self.assertEqual(
            (ngrams[0]["left"], ngrams[0]["keyword"], ngrams[0]["right"]),
            (["faol"], ["xotin-qizlar"], ["uchun"]),
        )

    def test_skips_annotation_markers(self):
        ngrams = find_ngrams("$$Toshkent$$ [Ali] bilan", "toshkent", before=0, after=2)
        self.assertEqual(ngrams[0]["right"], ["ali", "bilan"])


class SearchModeTests(TestCase):
    def setUp(self):
        self.paper = Newspaper.objects.create(title="Search Paper")
        Article.objects.create(
            title="One", newspaper=self.paper, language=Article.UZBEK, published_year=2001,
            content="Kitob o'qing. Kitob olamga oyna. Kitoblarga qarang.",
        )
        Article.objects.create(
            title="Two", newspaper=self.paper, language=Article.UZBEK, published_year=2002,
            content="Kitob o'qing, dedi \u041eʻzbekiston $$KPSS Markaziy Komiteti$$ a'zosi.",
        )

    def test_search_defaults_to_uzbek(self):
        for mode in ("concordance", "ngram"):
            for language_params in ({}, {"language": ""}):
                with self.subTest(mode=mode, language_params=language_params):
                    response = self.client.get(
                        "/search", {"q": "kitob", "mode": mode, **language_params}
                    )
                    self.assertEqual(response.status_code, 200)
                    self.assertGreater(response.context["results"]["total_frequency"], 0)
                    self.assertContains(response, '<option value="2" selected>Uzbek</option>', html=True)

    def test_search_preserves_explicit_english_selection(self):
        for mode in ("concordance", "ngram"):
            with self.subTest(mode=mode):
                response = self.client.get(
                    "/search", {"q": "kitob", "mode": mode, "language": 1}
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["results"]["total_frequency"], 0)
                self.assertContains(response, '<option value="1" selected>English</option>', html=True)
                self.assertContains(response, '<option value="2">Uzbek</option>', html=True)

    def test_db_prefilter_handles_homoglyphs_and_phrases(self):
        results = Article.objects.search("O'zbekiston", Article.UZBEK)
        self.assertEqual([r["article"].title for r in results["results"]], ["Two"])
        results = Article.objects.search("KPSS Markaziy Komiteti", Article.UZBEK)
        self.assertEqual(results["total_frequency"], 1)

    def test_db_prefilter_matches_hyphen_compounds_from_word_stats(self):
        Article.objects.create(
            title="Three", newspaper=self.paper, language=Article.UZBEK,
            content="Faol xotin-qizlar uchun.",
        )
        results = Article.objects.search("xotinqizlar", Article.UZBEK)
        self.assertEqual(results["total_frequency"], 1)

    def test_ngram_search_groups_and_counts(self):
        result = Article.objects.ngram_search("kitob", Article.UZBEK, before=0, after=1)
        top = result["ngrams"][0]
        self.assertEqual((top["text"], top["count"], top["article_count"]), ("kitob o'qing", 2, 2))
        self.assertEqual(result["total_frequency"], 4)
        self.assertEqual(result["year_totals"], {2001: 3, 2002: 1})

        exact = Article.objects.ngram_search("kitob", Article.UZBEK, after=1, match_type=1)
        self.assertEqual(exact["total_frequency"], 3)

    def test_search_view_ngram_mode_and_csv(self):
        params = {"q": "kitob", "language": 2, "mode": "ngram", "before": 0, "after": 1}
        response = self.client.get("/search", params)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "o&#x27;qing")
        self.assertEqual(response.context["ngram_count"], 3)

        response = self.client.get("/search", {**params, "format": "csv"})
        rows = list(csv.reader(io.StringIO(response.content.decode())))
        self.assertEqual(rows[0], ["ngram", "left", "keyword", "right", "count", "articles"])
        self.assertEqual(rows[1], ["kitob o'qing", "", "kitob", "o'qing", "2", "2"])

    def test_window_params_are_clamped(self):
        response = self.client.get(
            "/search", {"q": "kitob", "language": 2, "mode": "ngram", "before": "99", "after": "x"}
        )
        self.assertEqual((response.context["before"], response.context["after"]), (5, 1))


class StatDetailsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.paper = Newspaper.objects.create(title="Detail Paper")
        Article.objects.create(
            title="En", newspaper=self.paper, language=Article.ENGLISH, published_year=2020,
            content="alpha beta alpha [John] $$Paris$$",
        )
        self.uz = Article.objects.create(
            title="Uz", newspaper=self.paper, language=Article.UZBEK, published_year=2021,
            content="salom salom dunyo ^^Malika^^ $$Toshkent$$",
        )

    def test_dashboard_payload_has_card_details(self):
        details = self.client.get("/word_frequency_data").json()["summary"]["details"]
        self.assertEqual(
            set(details), {"words", "unique_words", "ttr", "hapax", "anthroponyms", "toponyms"}
        )
        self.assertIn("unique words ÷ total words", details["ttr"]["formula"])
        chips = details["toponyms"]["sections"][-2]["chips"]
        self.assertEqual(chips[0]["label"], "Toshkent")
        self.assertIn("language=2", chips[0]["href"])

    def test_pages_render_card_details(self):
        for url in ["/", f"/article/{self.uz.pk}", "/year/2021", f"/newspaper/{self.paper.pk}"]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertContains(response, 'data-stat-key="toponyms"')
            self.assertIn("stat_details", response.context)

        index_details = self.client.get("/").context["stat_details"]
        self.assertEqual(index_details["articles"]["sections"][0]["rows"][1]["value"], "1")

    def test_newspaper_chart_items_carry_language(self):
        payload = self.client.get(f"/newspaper/{self.paper.pk}/frequency_data").json()
        words = {item["word"]: item["language"] for item in payload["words"]}
        self.assertEqual(words["alpha"], int(Article.ENGLISH))
        self.assertEqual(words["salom"], int(Article.UZBEK))
        toponyms = {item["name"]: item["language"] for item in payload["toponyms"]["frequency"]}
        self.assertEqual(toponyms, {"Paris": 1, "Toshkent": 2})
