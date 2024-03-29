from django.http import HttpRequest, HttpResponse, JsonResponse, FileResponse
from django.shortcuts import render
from main_app.models import Article, Newspaper, create_frequency_csv
from main_app.types import SearchResult
from main_app.utils import filter_by_match_type, frequency_stats, word_count

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
    match_type = int(request.GET.get("match_type") or 0)
    print(f"match_type: {match_type}")
    # get search results
    results: SearchResult = Article.objects.search(query, language, year)
    if match_type != 0:
        results = filter_by_match_type(results, match_type)
    # render search results
    return render(
        request, "search.html", {"results": results, "match_type": match_type}
    )


def article_detail(request, article_id):
    """
    Article detail view
    """
    # get article
    article = Article.objects.get(id=article_id)
    # render article detail
    return render(
        request,
        "article_detail.html",
        {
            "article": article,
            "word_frequency": frequency_stats([article]),
            "word_count": word_count([article]).total_words,
        },
    )


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
    return JsonResponse(
        frequency_stats([Article.objects.get(id=article_id)])[:20], safe=False
    )


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

    english = Article.objects.filter(
        language=Article.ENGLISH, published_year=f"{year}-01-01"
    )
    uzbek = Article.objects.filter(
        language=Article.UZBEK, published_year=f"{year}-01-01"
    )

    # render year archive
    return render(
        request,
        "year_archive.html",
        {
            "english_article_count": english.count(),
            "english_frequency": frequency_stats(english),
            "total_english_words": word_count(english).total_words,
            "uzbek_article_count": uzbek.count(),
            "uzbek_frequency": frequency_stats(uzbek),
            "total_uzbek_words": word_count(uzbek).total_words,
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
            "article_count": newspaper.article_set.count(),
            "word_count": newspaper.article_set.count() * 500,
            "word_frequency": frequency_stats(newspaper.article_set.all()),
        },
    )


def newspaper_frequency(request, newspaper_id) -> JsonResponse:
    """
    return json object of word frequency data
    """
    return JsonResponse(
        frequency_stats(Article.objects.filter(newspaper_id=newspaper_id)[:20]),
        safe=False,
    )


def author(request):
    """
    Author view that returns pdf file
    """
    response = FileResponse(open("author.pdf", "rb"), content_type="application/pdf")
    response["Content-Disposition"] = "attachment; filename=NozimjonAtaboyevCV.pdf"
    return response
