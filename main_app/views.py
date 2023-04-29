from django.http import HttpRequest, JsonResponse
from django.shortcuts import render

from main_app.models import Article, Newspaper
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
        "word_frequency": frequency_stats(Article.objects.all())
    }
    return render(request, "index.html", context)


# search view
def search(request:HttpRequest):
    """
    Search view for searching articles
    """
    # get search query
    print("GET ", request.GET)
    query = request.GET.get("q")
    # get search results
    results = Article.objects.search(query)
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

def word_frequency_data(request) -> JsonResponse:
    """
    return json object of word frequency data
    """
    return JsonResponse(frequency_stats(Article.objects.all())[:20], safe=False)


def article_frequency(request, article_id) -> JsonResponse:
    """
    return json object of word frequency data
    """
    return JsonResponse(frequency_stats([Article.objects.get(id=article_id)])[:20], safe=False)