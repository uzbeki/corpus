from django.shortcuts import render

from main_app.models import Article, Newspaper


# index view
def index(request):
    """
    Index view for main page
    """
    context = {
        "newspapers": Newspaper.objects.prefetch_related("article_set")
    }
    return render(request, "index.html", context)


# search view
def search(request):
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
    return render(request, "article_detail.html", {"article": article})