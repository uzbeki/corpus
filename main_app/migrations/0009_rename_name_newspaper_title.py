# Generated by Django 4.2 on 2023-09-10 06:49

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("main_app", "0008_alter_article_options_article_word_count_total_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="newspaper",
            old_name="name",
            new_name="title",
        ),
    ]