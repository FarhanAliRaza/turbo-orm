# Generated migration for turbo-orm benchmark

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Article",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                ("content", models.TextField()),
                ("author", models.CharField(max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("view_count", models.IntegerField(default=0)),
                ("is_published", models.BooleanField(default=False)),
            ],
        ),
    ]
