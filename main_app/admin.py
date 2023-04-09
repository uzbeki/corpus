from django.contrib import admin
from main_app.models import Article, Newspaper

# Newspaper admin with Article inline
class ArticleInline(admin.TabularInline):
    model = Article
    extra = 1

class NewspaperAdmin(admin.ModelAdmin):
    inlines = [ArticleInline]

admin.site.register(Newspaper, NewspaperAdmin)
