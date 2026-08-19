# ruff: noqa: E501
from __future__ import annotations

import inspect
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Literal, NotRequired, TypedDict

from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Field, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.template.loader import get_template
from django.urls import path, reverse
from django.urls.resolvers import URLPattern
from wagtail import hooks
from wagtail.admin.menu import MenuItem
from wagtail.fields import StreamField
from wagtail.models import Page, Site, get_page_models

ACCESS_PERMISSION_APP_LABEL: str = "wagtail_developer_reference"
ACCESS_PERMISSION_CODENAME: str = "access_developer_reference"
ACCESS_PERMISSION_MODEL: str = "developerreferencepermission"
FieldCategory = Literal["structure", "metadata"]
ComponentType = Literal["PAGE", "BLOCK"]


class UsageData(TypedDict):
    live: int
    total: int
    draft: int


class FieldInfo(TypedDict):
    label: str
    type: str
    block_name: NotRequired[str | None]


class FieldGroups(TypedDict):
    structure: list[FieldInfo]
    metadata: list[FieldInfo]


class AuditItem(TypedDict):
    site_id: int
    site_name: str
    hierarchy: str
    clean_name: str
    type: ComponentType
    fields: FieldGroups
    usage: UsageData
    template: str | None
    template_label: str | None


def user_can_access_developer_reference(user: Any) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if not getattr(user, "is_active", False):
        return False

    user_has_permission = user.user_permissions.filter(
        codename=ACCESS_PERMISSION_CODENAME,
        content_type__app_label=ACCESS_PERMISSION_APP_LABEL,
        content_type__model=ACCESS_PERMISSION_MODEL,
    ).exists()
    group_has_permission = user.groups.filter(
        permissions__codename=ACCESS_PERMISSION_CODENAME,
        permissions__content_type__app_label=ACCESS_PERMISSION_APP_LABEL,
        permissions__content_type__model=ACCESS_PERMISSION_MODEL,
    ).exists()
    return user_has_permission or group_has_permission


def require_developer_reference_access(user: Any) -> bool:
    if user_can_access_developer_reference(user):
        return True
    raise PermissionDenied


class WagtailAuditor:
    def __init__(self) -> None:
        self.results: list[AuditItem] = []
        self.seen_blocks: set[str] = set()
        self.all_page_models: list[type[Page]] = get_page_models()
        self.sites: Iterable[Site] = Site.objects.all()
        self.models_with_streamfields: list[type[Page]] = [
            model
            for model in self.all_page_models
            if any(isinstance(field, StreamField) for field in model._meta.get_fields())
        ]
        self.excluded_fields: set[str] = {
            "path",
            "depth",
            "numchild",
            "content_type",
            "page_ptr",
            "go_live_at",
            "expire_at",
            "show_in_menus",
            "first_published_at",
            "last_published_at",
            "latest_revision_created_at",
        }

    def get_template_path(self, template_name: str | None) -> str | None:
        if not template_name:
            return None
        try:
            return get_template(template_name).origin.name
        except Exception:
            return template_name

    def get_template_label(self, template_path: str | None) -> str | None:
        return Path(template_path).name if template_path else None


    def _analyze_model_field(self, field: Field[Any, Any]) -> tuple[FieldInfo | None, FieldCategory | None]:
        if field.name in self.excluded_fields or (field.is_relation and not field.many_to_one):
            return None, None
        field_type = type(field).__name__
        category: FieldCategory = "structure" if isinstance(field, StreamField) or "RichTextField" in field_type else "metadata"
        return {"label": str(getattr(field, "verbose_name", field.name)).capitalize(), "type": field_type}, category

    def get_internal_structure(self, object_instance: Any) -> FieldGroups:
        structure_fields: list[FieldInfo] = []
        metadata_fields: list[FieldInfo] = []

        if hasattr(object_instance, "child_blocks"):
            for name, block in object_instance.child_blocks.items():
                label = getattr(block.meta, "label", None) or name
                structure_fields.append(
                    {"label": str(label), "type": type(block).__name__}
                )
        elif hasattr(object_instance, "_meta"):
            for field in object_instance._meta.get_fields():
                info, category = self._analyze_model_field(field)
                if category == "structure":
                    structure_fields.append(info)
                elif category == "metadata":
                    metadata_fields.append(info)

        return {"structure": structure_fields, "metadata": metadata_fields}

    def _get_usage_for_site(
        self,
        model: type[Page],
        site: Site,
        block_name: str | None = None,
    ) -> UsageData:
        queryset = model.objects.descendant_of(site.root_page)
        if block_name:
            search_key = f'"{block_name}"'
            fields = model._meta.get_fields()
            stream_fields: list[str] = [
                f.name for f in fields if isinstance(f, StreamField)
            ]
            total_count = 0
            live_count = 0
            for field_name in stream_fields:
                total_count += queryset.filter(
                    **{f"{field_name}__icontains": search_key}
                ).count()
                live_count += queryset.live().filter(
                    **{f"{field_name}__icontains": search_key}
                ).count()
        else:
            total_count = queryset.count()
            live_count = queryset.live().count()
        return {
            "live": live_count,
            "total": total_count,
            "draft": total_count - live_count,
        }

    def process_block(self, block_name: str, block_object: Any, parent_label: str, site: Site, include_usage: bool = False) -> None:
        is_class = inspect.isclass(block_object)
        block_class = block_object.__name__ if is_class else block_object.__class__.__name__
        signature = f"{site.id}_{parent_label}_{block_class}_{block_name}"
        if signature in self.seen_blocks:
            return
        block_label = str(getattr(block_object.meta, "label", None) or block_name)
        template_path = self.get_template_path(getattr(block_object.meta, "template", None))
        usage = {"live": 0, "total": 0, "draft": 0}
        if include_usage:
            for model in self.models_with_streamfields:
                model_usage = self._get_usage_for_site(model, site, block_name)
                for key in usage:
                    usage[key] += model_usage[key]
        self.results.append({"site_id": site.id, "site_name": site.site_name, "hierarchy": f"{parent_label} → {block_label}", "clean_name": block_name, "type": "BLOCK", "fields": self.get_internal_structure(block_object), "usage": usage, "template": template_path, "template_label": self.get_template_label(template_path)})
        self.seen_blocks.add(signature)
        for child_name, child_object in getattr(block_object, "child_blocks", {}).items():
            self.process_block(child_name, child_object, f"{parent_label} → {block_label}", site, include_usage)

    def run(self, include_usage: bool = False) -> list[AuditItem]:
        for site in self.sites:
            for model in self.all_page_models:
                usage_data = self._get_usage_for_site(model, site) if include_usage else {"live": 0, "total": 0, "draft": 0}
                default_tpl = f"{model._meta.app_label}/{model._meta.model_name}.html"
                template_path = self.get_template_path(
                    getattr(model, "template", default_tpl)
                )
                self.results.append(
                    {
                        "site_id": site.id,
                        "site_name": site.site_name,
                        "hierarchy": str(model._meta.verbose_name).title(),
                        "clean_name": model.__name__,
                        "type": "PAGE",
                        "fields": self.get_internal_structure(model),
                        "usage": usage_data,
                        "template": template_path,
                        "template_label": self.get_template_label(template_path),
                    }
                )
                for field in model._meta.get_fields():
                    if isinstance(field, StreamField):
                        child_blocks = field.stream_block.child_blocks.items()
                        for block_name, block_object in child_blocks:
                            self.process_block(
                                block_name,
                                block_object,
                                str(model._meta.verbose_name).title(),
                                site,
                                include_usage,
                            )
        return self.results


@user_passes_test(require_developer_reference_access)
def developer_reference_view(request: HttpRequest) -> HttpResponse:
    applied = request.GET.get("apply") == "1"
    auditor = WagtailAuditor()
    audit_results = auditor.run(include_usage=applied)
    quick_search_by_component = {}
    for item in audit_results:
        key = (item["type"], item["hierarchy"])
        quick_search_by_component.setdefault(key, (item["type"], item["hierarchy"], item["hierarchy"]))
    quick_search_items = sorted(quick_search_by_component.values(), key=lambda item: (item[2].casefold(), item[0]))
    filters = {"q": request.GET.get("q", "").strip(), "type": request.GET.get("type", "ALL"), "site": request.GET.get("site", ""), "min_usage": request.GET.get("min_usage", ""), "max_usage": request.GET.get("max_usage", "")}
    error = ""
    filtered_results: list[AuditItem] = []
    if applied:
        try:
            minimum = int(filters["min_usage"]) if filters["min_usage"] else None
            maximum = int(filters["max_usage"]) if filters["max_usage"] else None
            if (minimum is not None and minimum < 0) or (maximum is not None and maximum < 0) or (minimum is not None and maximum is not None and minimum > maximum):
                raise ValueError
        except ValueError:
            error = "Usage range must contain non-negative numbers, with min no greater than max."
            minimum = maximum = None
        if not error:
            query = filters["q"].casefold()
            for item in audit_results:
                matches_query = not query or query in " ".join((item["site_name"], item["hierarchy"], item["clean_name"])).casefold()
                matches_type = filters["type"] == "ALL" or item["type"] == filters["type"]
                matches_site = not filters["site"] or str(item["site_id"]) == filters["site"]
                total = item["usage"]["total"]
                matches_min = minimum is None or total >= minimum
                matches_max = maximum is None or total <= maximum
                if matches_query and matches_type and matches_site and matches_min and matches_max:
                    filtered_results.append(item)
    return render(request, "index.html", {"audit_data": sorted(filtered_results, key=lambda item: (item["site_name"], item["hierarchy"])), "quick_search_items": quick_search_items, "sites": Site.objects.order_by("site_name", "id"), "filters": filters, "is_applied": applied, "filter_error": error})


@user_passes_test(require_developer_reference_access)
def developer_usage_detail_view(
    request: HttpRequest,
    component_type: str,
    component_name: str,
) -> HttpResponse:
    site_filter = request.GET.get("site")
    site = Site.objects.filter(pk=site_filter).first()
    pages = Page.objects.none()

    # Do not load every matching page into Python. Scope the query to the site
    # and let the database return only the current results page.
    if site_filter:
        site_pages = (
            Page.objects.descendant_of(site.root_page) if site else Page.objects.none()
        )
    else:
        site_pages = Page.objects.all()
    if component_type == "PAGE":
        target_model = next(
            (model for model in get_page_models() if model.__name__ == component_name),
            None,
        )
        if target_model:
            pages = site_pages.filter(pk__in=target_model.objects.values("pk"))
    else:
        search_key = f'"{component_name}"'
        component_filter = Q()
        for model in get_page_models():
            stream_fields = [
                f.name
                for f in model._meta.get_fields()
                if isinstance(f, StreamField)
            ]
            for field_name in stream_fields:
                component_filter |= Q(
                    pk__in=model.objects.filter(
                        **{f"{field_name}__icontains": search_key}
                    ).values("pk")
                )
        if component_filter:
            pages = site_pages.filter(component_filter)

    search_query = request.GET.get("q", "").strip()
    if search_query:
        pages = pages.filter(
            Q(title__icontains=search_query) | Q(slug__icontains=search_query)
        )

    paginator = Paginator(pages.order_by("title", "pk").distinct(), 50)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "detail.html",
        {
            "component_name": component_name,
            "pages": page_obj,
            "page_obj": page_obj,
            "search_query": search_query,
            "site_filter": site_filter or "",
        },
    )


@hooks.register("register_admin_urls")
def register_admin_urls() -> list[URLPattern]:
    return [
        path("developer-reference/", developer_reference_view, name="dev_reference"),
        path(
            "developer-reference/<str:component_type>/<str:component_name>/",
            developer_usage_detail_view,
            name="dev_usage_detail",
        ),
    ]


class DeveloperReferenceMenuItem(MenuItem):
    def is_shown(self, request: HttpRequest) -> bool:
        return user_can_access_developer_reference(request.user)


@hooks.register("register_admin_menu_item")
def register_menu() -> MenuItem:
    url = reverse("dev_reference")
    return DeveloperReferenceMenuItem(
        "System Registry",
        url,
        icon_name="code",
        order=10000,
    )
