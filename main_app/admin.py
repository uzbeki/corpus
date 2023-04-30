from django.contrib import admin
from main_app.models import Article, Newspaper

# admin.site.site_title = 'Site Administration'
admin.site.site_header = 'corpus.bekhruz.com'

class ArticleInline(admin.TabularInline):
    model = Article
    extra = 1

class NewspaperAdmin(admin.ModelAdmin):
    inlines = [ArticleInline]

admin.site.register(Newspaper, NewspaperAdmin)


