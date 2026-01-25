# django url patterns with /search
from django.urls import path, register_converter
from main_app.path_converters import FourDigitYearConverter
from . import views

register_converter(FourDigitYearConverter, "yyyy")
urlpatterns = [
    path("", views.index, name="index"),
    path("placeholders/geo/<int:seed>.svg", views.geo_placeholder_svg, name="geo_placeholder_svg"),
    path("search", views.search_new, name="search"),
    path("search-new", views.search_new, name="search_new"),
    path("search-old", views.search, name="search_old"),
    path("a", views.handle_csv_upload_view, name="a"),
    path("article/<int:article_id>", views.article_detail, name="article_detail"),
    path("word_frequency_data", views.word_frequency_data, name="word_frequency_data"),
    path("article/<int:article_id>/frequency_data", views.article_frequency, name="article_frequency"),
    path("year/<yyyy:year>", views.year_archive, name="year_archive"),
    path("year/<yyyy:year>/<str:language>/download", views.year_archive_download, name="year_archive_download"),
    path("newspaper/<int:newspaper_id>", views.newspaper_detail, name="newspaper_detail"),
    path("newspaper/<int:newspaper_id>/frequency_data", views.newspaper_frequency, name="newspaper_frequency"),
    path("author", views.author, name="author"),
]