# Generated by Django 4.2 on 2023-09-10 10:45

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("main_app", "0009_rename_name_newspaper_title"),
    ]

    operations = [
        migrations.AlterField(
            model_name="newspaper",
            name="published_year",
            field=models.DateField(blank=True, default=None, null=True),
        ),
    ]
