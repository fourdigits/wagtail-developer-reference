from __future__ import annotations

from django.db import models


class DeveloperReferencePermission(models.Model):
    class Meta:
        default_permissions: tuple[str, ...] = ()
        managed: bool = False
        permissions: tuple[tuple[str, str], ...] = (
            (
                "access_developer_reference",
                "Can access the Wagtail developer reference",
            ),
        )
        verbose_name: str = "developer reference access"
        verbose_name_plural: str = "developer reference access"
