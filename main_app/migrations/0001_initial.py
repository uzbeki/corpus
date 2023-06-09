# Generated by Django 4.2 on 2023-04-08 09:55

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Newspaper",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("link", models.URLField(blank=True, null=True)),
                ("published_year", models.DateField()),
                ("issue_number", models.IntegerField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="Article",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=100)),
                ("author", models.CharField(blank=True, max_length=100, null=True)),
                ("content", models.TextField(max_length=505)),
                (
                    "newspaper",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="main_app.newspaper",
                    ),
                ),
            ],
        ),
    ]
