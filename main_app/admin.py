from django.contrib import admin
from main_app.models import Article, Newspaper

# admin.site.site_title = 'Site Administration'
admin.site.site_header = 'corpus.bekhruz.com'

class ArticleInline(admin.TabularInline):
    model = Article
    extra = 1

class NewspaperAdmin(admin.ModelAdmin):
    inlines = [ArticleInline]
    search_fields = ("title",)

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
    date_hierarchy = "published_year"
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


admin.site.register(Newspaper, NewspaperAdmin)


