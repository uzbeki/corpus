from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.core.files.uploadedfile import UploadedFile
from urllib3 import HTTPResponse
from main_app.models import Article, Newspaper, create_frequency_csv
from main_app.types import FrequencyStats
from main_app.utils import frequency_stats

# from main_app.utils import frequency_stats as f


# index view
def index(request):
    """
    Index view for main page
    """
    context = {
        "newspapers": Newspaper.objects.prefetch_related("article_set"),
        "word_frequency": frequency_stats(Article.objects.all()),
        "article_count": Article.objects.count(),
        "word_count": Article.objects.count() * 500,
        "published_years": Article.objects.values("published_year")
        .distinct()
        .order_by("published_year")
        .values_list("published_year", flat=True),
        # "unique_word_count": Article.objects.unique_word_count(),
    }
    return render(request, "index.html", context)


# search view
def search(request: HttpRequest):
    """
    Search view for searching articles
    """
    # get search query
    query = request.GET.get("q")
    language = int(request.GET.get("language"))
    year = request.GET.get("year") or None
    # get search results
    results = Article.objects.search(query, language, year)
    # render search results
    return render(request, "search.html", {"results": results})


def article_detail(request, article_id):
    """
    Article detail view
    """
    # get article
    article = Article.objects.get(id=article_id)
    # render article detail
    return render(request, "article_detail.html", {"article": article, "word_frequency": frequency_stats([article])})


def word_frequency_data(request: HttpRequest) -> JsonResponse | HttpResponse:
    """
    return json object of word frequency data
    """

    # check if "full" parameter is passed
    if request.GET.get("full"):
        if request.GET.get("language") == "uzbek":
            # articles = Article.objects.filter(language=Article.UZBEK).create_frequency_csv()
            articles = Article.objects.create_frequency_csv(language=Article.UZBEK)
        else:
            # articles = Article.objects.filter(language=Article.ENGLISH).create_frequency_csv()
            articles = Article.objects.create_frequency_csv(language=Article.ENGLISH)
        return articles

    else:
        english = Article.objects.filter(language=Article.ENGLISH)
        uzbek = Article.objects.filter(language=Article.UZBEK)
        return JsonResponse(
            {
                "english": frequency_stats(english)[:20],
                "uzbek": frequency_stats(uzbek)[:20],
            },
            safe=False,
        )

    # return JsonResponse(frequency_stats(Article.objects.all())[:20], safe=False)


def article_frequency(request, article_id) -> JsonResponse:
    """
    return json object of word frequency data
    """
    return JsonResponse(frequency_stats([Article.objects.get(id=article_id)])[:20], safe=False)


def handle_csv_upload_view(request: HttpRequest):
    """
    Handle csv upload view
    """
    if request.method == "POST":
        # get csv file from request
        csv_file = request.FILES["file"]
        # print(csv_file)
        # print(dir(csv_file))
        # create article
        # Article.objects.create_from_csv(csv_file.read().decode("utf-8").splitlines())
        Article.objects.create_from_csv(csv_file)
    return render(request, "upload.html", {"newspapers": Newspaper.objects.all()})


def year_archive(request, year: int):
    """
    Year archive view
    """
    # get articles
    # articles = Article.objects.filter(published_year=f"{year}-01-01")

    # get english and uzbek articles separately

    english = Article.objects.filter(language=Article.ENGLISH, published_year=f"{year}-01-01")
    uzbek = Article.objects.filter(language=Article.UZBEK, published_year=f"{year}-01-01")

    # render year archive
    return render(
        request,
        "year_archive.html",
        {
            "english_articles": english,
            "english_frequency": frequency_stats(english),
            "uzbek_articles": uzbek,
            "uzbek_frequency": frequency_stats(uzbek),
            "year": year,
        },
    )


def year_archive_download(request, year: int, language: str):
    """
    Year archive view
    """
    # get articles
    articles = Article.objects.filter(published_year=f"{year}-01-01", language=language)
    csv_response = create_frequency_csv(articles, f"{year}_{language}_archieve.csv")

    # render year archive
    return csv_response


def newspaper_detail(request, newspaper_id):
    """
    Newspaper detail view
    """
    # get newspaper
    newspaper = Newspaper.objects.get(id=newspaper_id)
    # render newspaper detail
    return render(
        request,
        "newspaper_detail.html",
        {
            "newspaper": newspaper,
            "word_frequency": frequency_stats(newspaper.article_set.all()),
        },
    )


def newspaper_frequency(request, newspaper_id) -> JsonResponse:
    """
    return json object of word frequency data
    """
    return JsonResponse(
        frequency_stats(
            Article.objects.filter(newspaper_id=newspaper_id)[:20]
        ),
        safe=False,
    )
