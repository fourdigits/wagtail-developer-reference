from __future__ import annotations

from django.apps import AppConfig


class WagtailDeveloperReferenceConfig(AppConfig):
    default_auto_field: str = "django.db.models.BigAutoField"
    name: str = "wagtail_developer_reference"
    verbose_name: str = "Wagtail developer reference"
