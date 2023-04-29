# django url patterns with /search
from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("search", views.search, name="search"),
    path("article/<int:article_id>", views.article_detail, name="article_detail"),
    path("word_frequency_data", views.word_frequency_data, name="word_frequency_data"),
    path("article/<int:article_id>/frequency_data", views.article_frequency, name="article_frequency"),
]