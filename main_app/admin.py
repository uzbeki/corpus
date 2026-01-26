from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html
from main_app.models import Article, Newspaper

# admin.site.site_title = 'Site Administration'
admin.site.site_header = 'Zahri Corpus Admin Panel'

class ArticleInline(admin.TabularInline):
    model = Article
    extra = 1

class NewspaperAdmin(admin.ModelAdmin):
    list_display = ("title", "article_count", "public_link")
    search_fields = ("title",)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(article_count=Count("article"))

    @admin.display(description="Articles", ordering="article_count")
    def article_count(self, obj: Newspaper):
        return obj.article_count

    @admin.display(description="Public page")
    def public_link(self, obj: Newspaper):
        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer">View</a>',
            obj.get_absolute_url(),
        )

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "newspaper",
        "published_year",
        "language",
        "author_short",
        "word_count",
        "annotated_male_count",
        "annotated_female_count",
        "public_link",
    )
    list_select_related = ("newspaper",)
    search_fields = (
        "title",
        "author",
        "newspaper__title",
    )
    list_filter = (
        "language",
        "published_year",
        "newspaper",
    )
    ordering = ("-published_year", "newspaper__title", "title")
    autocomplete_fields = ("newspaper",)
    list_per_page = 25

    @admin.display(description="Author")
    def author_short(self, obj: Article):
        return (obj.author or "").strip()[:50]

    @admin.display(description="Words")
    def word_count(self, obj: Article):
        return len((obj.content or "").split())

    @admin.display(description="Male names")
    def annotated_male_count(self, obj: Article):
        return obj.annotated_name_counts().get("male", 0)

    @admin.display(description="Female names")
    def annotated_female_count(self, obj: Article):
        return obj.annotated_name_counts().get("female", 0)

    @admin.display(description="Public page")
    def public_link(self, obj: Article):
        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer">View</a>',
            obj.get_absolute_url(),
        )


admin.site.register(Newspaper, NewspaperAdmin)


