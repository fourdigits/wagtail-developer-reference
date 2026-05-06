# Generated manually for wagtail-developer-reference.

from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="DeveloperReferencePermission",
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
            ],
            options={
                "verbose_name": "developer reference access",
                "verbose_name_plural": "developer reference access",
                "permissions": (
                    (
                        "access_developer_reference",
                        "Can access the Wagtail developer reference",
                    ),
                ),
                "default_permissions": (),
                "managed": False,
            },
        ),
    ]
