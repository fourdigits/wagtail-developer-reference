from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Optional, TypedDict
from urllib.parse import urlencode

from django.contrib.auth.decorators import user_passes_test
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Field, Q, QuerySet, TextField
from django.db.models.functions import Cast
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import get_template
from django.urls import path, reverse
from django.urls.resolvers import URLPattern
from wagtail import hooks
from wagtail.admin.menu import MenuItem
from wagtail.blocks import ListBlock, StreamBlock, StructBlock
from wagtail.fields import StreamField
from wagtail.models import Page, Site, get_page_models

ACCESS_PERMISSION_APP_LABEL = "wagtail_developer_reference"
ACCESS_PERMISSION_CODENAME = "access_developer_reference"
ACCESS_PERMISSION_MODEL = "developerreferencepermission"
FieldCategory = Literal["structure", "metadata"]
ComponentType = Literal["PAGE", "BLOCK"]


class UsageData(TypedDict):
    live: int
    total: int
    draft: int


class FieldInfo(TypedDict):
    label: str
    type: str


class FieldGroups(TypedDict):
    structure: list[FieldInfo]
    metadata: list[FieldInfo]


@dataclass(frozen=True)
class ComponentDefinition:
    definition_id: str
    component_type: ComponentType
    hierarchy: str
    clean_name: str
    model_label: str
    stream_field: Optional[str]
    block_path: tuple[str, ...]
    fields: FieldGroups
    template: Optional[str]
    template_label: Optional[str]


class AuditItem(TypedDict):
    definition_id: str
    site_id: Optional[int]
    site_name: str
    hierarchy: str
    clean_name: str
    type: ComponentType
    fields: FieldGroups
    usage: UsageData
    template: Optional[str]
    template_label: Optional[str]


def empty_usage() -> UsageData:
    return {"live": 0, "total": 0, "draft": 0}


def user_can_access_developer_reference(user: Any) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if not getattr(user, "is_active", False):
        return False
    return user.user_permissions.filter(
        codename=ACCESS_PERMISSION_CODENAME,
        content_type__app_label=ACCESS_PERMISSION_APP_LABEL,
        content_type__model=ACCESS_PERMISSION_MODEL,
    ).exists() or user.groups.filter(
        permissions__codename=ACCESS_PERMISSION_CODENAME,
        permissions__content_type__app_label=ACCESS_PERMISSION_APP_LABEL,
        permissions__content_type__model=ACCESS_PERMISSION_MODEL,
    ).exists()


def require_developer_reference_access(user: Any) -> bool:
    if user_can_access_developer_reference(user):
        return True
    raise PermissionDenied


class WagtailAuditor:
    def __init__(self) -> None:
        self.all_page_models = list(get_page_models())
        self.models_by_label = {
            model._meta.label_lower: model for model in self.all_page_models
        }
        self._nested_paths_cache: dict[int, tuple[str, ...]] = {}
        self.excluded_fields = {
            "path", "depth", "numchild", "content_type", "page_ptr",
            "go_live_at", "expire_at", "show_in_menus", "first_published_at",
            "last_published_at", "latest_revision_created_at",
        }

    @staticmethod
    def get_template_path(template_name: Optional[str]) -> Optional[str]:
        if not template_name:
            return None
        try:
            return get_template(template_name).origin.name
        except Exception:
            return template_name

    @staticmethod
    def get_template_label(template_path: Optional[str]) -> Optional[str]:
        return Path(template_path).name if template_path else None

    def _analyze_model_field(
        self, field: Field[Any, Any]
    ) -> tuple[Optional[FieldInfo], Optional[FieldCategory]]:
        if field.name in self.excluded_fields or (
            field.is_relation and not field.many_to_one
        ):
            return None, None
        field_type = type(field).__name__
        category: FieldCategory = (
            "structure"
            if isinstance(field, StreamField) or "RichTextField" in field_type
            else "metadata"
        )
        return {
            "label": str(getattr(field, "verbose_name", field.name)).capitalize(),
            "type": field_type,
        }, category

    def get_internal_structure(self, instance: Any) -> FieldGroups:
        structure_fields: list[FieldInfo] = []
        metadata_fields: list[FieldInfo] = []
        if hasattr(instance, "child_blocks"):
            for name, block in instance.child_blocks.items():
                label = getattr(block.meta, "label", None) or name
                structure_fields.append(
                    {"label": str(label), "type": type(block).__name__}
                )
        elif hasattr(instance, "_meta"):
            for field in instance._meta.get_fields():
                info, category = self._analyze_model_field(field)
                if info is not None and category == "structure":
                    structure_fields.append(info)
                elif info is not None and category == "metadata":
                    metadata_fields.append(info)
        return {"structure": structure_fields, "metadata": metadata_fields}

    @staticmethod
    def _definition_id(
        component_type: ComponentType,
        model_label: str,
        stream_field: Optional[str] = None,
        block_path: tuple[str, ...] = (),
    ) -> str:
        identity = ":".join(
            (component_type, model_label, stream_field or "", "/".join(block_path))
        )
        return hashlib.sha256(identity.encode()).hexdigest()[:20]

    def _walk_block(
        self,
        definitions: list[ComponentDefinition],
        model: type[Page],
        stream_field: str,
        block_name: str,
        block: Any,
        parent_hierarchy: str,
        block_path: tuple[str, ...],
    ) -> None:
        block_label = str(getattr(block.meta, "label", None) or block_name)
        hierarchy = f"{parent_hierarchy} → {block_label}"
        template_path = self.get_template_path(getattr(block.meta, "template", None))
        definitions.append(ComponentDefinition(
            definition_id=self._definition_id(
                "BLOCK", model._meta.label_lower, stream_field, block_path
            ),
            component_type="BLOCK",
            hierarchy=hierarchy,
            clean_name=block_name,
            model_label=model._meta.label_lower,
            stream_field=stream_field,
            block_path=block_path,
            fields=self.get_internal_structure(block),
            template=template_path,
            template_label=self.get_template_label(template_path),
        ))
        child_blocks = getattr(block, "child_blocks", None)
        if child_blocks:
            for child_name, child_block in child_blocks.items():
                self._walk_block(
                    definitions, model, stream_field, child_name, child_block,
                    hierarchy, (*block_path, child_name),
                )
            return
        child_block = getattr(block, "child_block", None)
        nested_children = getattr(child_block, "child_blocks", None)
        if nested_children:
            for child_name, nested_block in nested_children.items():
                self._walk_block(
                    definitions, model, stream_field, child_name, nested_block,
                    hierarchy, (*block_path, child_name),
                )

    def _build_definition_catalog(self) -> tuple[ComponentDefinition, ...]:
        definitions: list[ComponentDefinition] = []
        for model in self.all_page_models:
            hierarchy = str(model._meta.verbose_name).title()
            template_path = self.get_template_path(getattr(
                model, "template",
                f"{model._meta.app_label}/{model._meta.model_name}.html",
            ))
            definitions.append(ComponentDefinition(
                definition_id=self._definition_id("PAGE", model._meta.label_lower),
                component_type="PAGE",
                hierarchy=hierarchy,
                clean_name=model.__name__,
                model_label=model._meta.label_lower,
                stream_field=None,
                block_path=(),
                fields=self.get_internal_structure(model),
                template=template_path,
                template_label=self.get_template_label(template_path),
            ))
            for field in model._meta.get_fields():
                if isinstance(field, StreamField):
                    for block_name, block in field.stream_block.child_blocks.items():
                        self._walk_block(
                            definitions, model, field.name, block_name, block,
                            hierarchy, (block_name,),
                        )
        return tuple(definitions)

    @classmethod
    @lru_cache(maxsize=1)
    def definition_catalog(cls) -> tuple[ComponentDefinition, ...]:
        return cls()._build_definition_catalog()

    @classmethod
    def clear_definition_cache(cls) -> None:
        cls.definition_catalog.cache_clear()

    @staticmethod
    def site_name(site: Optional[Site]) -> str:
        if site is None:
            return "All sites"
        name = site.site_name
        if isinstance(name, (tuple, list)) and len(name) == 1:
            name = name[0]
        return str(name or site.hostname)

    def _nested_site_paths(self, site: Site) -> tuple[str, ...]:
        if site.pk not in self._nested_paths_cache:
            self._nested_paths_cache[site.pk] = tuple(
                Site.objects.exclude(root_page_id=site.root_page_id).filter(
                    root_page__path__startswith=site.root_page.path,
                    root_page__depth__gt=site.root_page.depth,
                ).values_list("root_page__path", flat=True)
            )
        return self._nested_paths_cache[site.pk]

    def _scope_page_queryset(self, site: Optional[Site]) -> QuerySet[Page]:
        queryset = Page.objects.all()
        if site is None:
            return queryset
        queryset = queryset.filter(path__startswith=site.root_page.path)
        for nested_path in self._nested_site_paths(site):
            queryset = queryset.exclude(path__startswith=nested_path)
        return queryset

    def _scope_model_queryset(
        self, model: type[Page], site: Optional[Site]
    ) -> QuerySet[Page]:
        queryset = model.objects.all()
        if site is None:
            return queryset
        queryset = queryset.filter(path__startswith=site.root_page.path)
        for nested_path in self._nested_site_paths(site):
            queryset = queryset.exclude(path__startswith=nested_path)
        return queryset

    def _collect_present_paths(
        self,
        block: Any,
        value: Any,
        prefix: tuple[str, ...],
        present: set[tuple[str, ...]],
    ) -> None:
        if isinstance(block, StreamBlock):
            if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
                return
            for bound_block in value:
                if isinstance(bound_block, Mapping):
                    block_name = bound_block.get("type")
                    block_value = bound_block.get("value")
                else:
                    block_name = getattr(bound_block, "block_type", None)
                    block_value = getattr(bound_block, "value", None)
                if not block_name or block_name not in block.child_blocks:
                    continue
                path_value = (*prefix, block_name)
                present.add(path_value)
                self._collect_present_paths(
                    block.child_blocks[block_name], block_value, path_value, present
                )
            return
        if isinstance(block, StructBlock):
            if not isinstance(value, Mapping):
                return
            for block_name, child_block in block.child_blocks.items():
                if block_name not in value:
                    continue
                path_value = (*prefix, block_name)
                present.add(path_value)
                self._collect_present_paths(
                    child_block, value[block_name], path_value, present
                )
            return
        if isinstance(block, ListBlock):
            if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
                return
            for child in value:
                if isinstance(child, Mapping) and "value" in child:
                    child_value = child["value"]
                else:
                    child_value = getattr(child, "value", child)
                self._collect_present_paths(
                    block.child_block, child_value, prefix, present
                )

    @staticmethod
    def _decode_stream_value(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return []

    def _get_present_paths(
        self, model: type[Page], stream_field: str, stream_value: Any
    ) -> set[tuple[str, ...]]:
        present: set[tuple[str, ...]] = set()
        field = model._meta.get_field(stream_field)
        self._collect_present_paths(
            field.stream_block, self._decode_stream_value(stream_value), (), present
        )
        return present

    def get_page_usage(
        self,
        definitions: Iterable[ComponentDefinition],
        site: Optional[Site],
    ) -> dict[str, UsageData]:
        selected = tuple(definitions)
        result = {item.definition_id: empty_usage() for item in selected}
        if not selected:
            return result
        model_definitions = {item.model_label: item for item in selected}
        models = [self.models_by_label[label] for label in model_definitions]
        content_types = ContentType.objects.get_for_models(
            *models, for_concrete_models=False
        )
        content_type_to_label = {
            content_type.pk: model._meta.label_lower
            for model, content_type in content_types.items()
        }
        grouped = self._scope_page_queryset(site).values(
            "content_type_id", "live"
        ).annotate(count=Count("pk"))
        all_pages_usage = empty_usage()
        for row in grouped:
            count = row["count"]
            all_pages_usage["total"] += count
            status_key = "live" if row["live"] else "draft"
            all_pages_usage[status_key] += count
            model_label = content_type_to_label.get(row["content_type_id"])
            if model_label in model_definitions:
                usage = result[model_definitions[model_label].definition_id]
                usage["total"] += count
                usage[status_key] += count
        page_definition = model_definitions.get(Page._meta.label_lower)
        if page_definition is not None:
            result[page_definition.definition_id] = all_pages_usage
        return result

    def get_block_usage(
        self,
        definitions: Iterable[ComponentDefinition],
        site: Optional[Site],
    ) -> dict[str, UsageData]:
        selected = tuple(definitions)
        result = {item.definition_id: empty_usage() for item in selected}
        groups: dict[
            str, dict[str, dict[tuple[str, ...], ComponentDefinition]]
        ] = {}
        for item in selected:
            if item.stream_field is None:
                continue
            groups.setdefault(item.model_label, {}).setdefault(
                item.stream_field, {}
            )[item.block_path] = item

        for model_label, field_groups in groups.items():
            model = self.models_by_label[model_label]
            field_names = tuple(field_groups)
            aliases = tuple(
                f"_wdr_stream_{index}" for index in range(len(field_names))
            )
            annotations = {
                alias: Cast(field_name, output_field=TextField())
                for alias, field_name in zip(aliases, field_names)
            }
            values = self._scope_model_queryset(model, site).annotate(
                **annotations
            ).values_list("live", *aliases)
            for row in values.iterator(chunk_size=200):
                is_live = row[0]
                for index, stream_field in enumerate(field_names, start=1):
                    definitions_by_path = field_groups[stream_field]
                    present_paths = self._get_present_paths(
                        model, stream_field, row[index]
                    )
                    for block_path in definitions_by_path.keys() & present_paths:
                        usage = result[
                            definitions_by_path[block_path].definition_id
                        ]
                        usage["total"] += 1
                        usage["live" if is_live else "draft"] += 1
        return result

    def calculate_usage(
        self,
        definitions: Iterable[ComponentDefinition],
        site: Optional[Site],
    ) -> dict[str, UsageData]:
        selected = tuple(definitions)
        page_definitions = [
            item for item in selected if item.component_type == "PAGE"
        ]
        block_definitions = [
            item for item in selected if item.component_type == "BLOCK"
        ]
        return {
            **self.get_page_usage(page_definitions, site),
            **self.get_block_usage(block_definitions, site),
        }

    def pages_for_definition(
        self, definition: ComponentDefinition, site: Optional[Site]
    ) -> QuerySet[Page]:
        scoped_pages = self._scope_page_queryset(site)
        model = self.models_by_label[definition.model_label]
        if definition.component_type == "PAGE":
            if model is Page:
                return scoped_pages
            content_type = ContentType.objects.get_for_model(
                model, for_concrete_model=False
            )
            return scoped_pages.filter(content_type_id=content_type.pk)
        if definition.stream_field is None:
            return Page.objects.none()
        prefilter = {
            f"{definition.stream_field}__icontains": f'"{definition.clean_name}"'
        }
        values = (
            self._scope_model_queryset(model, site)
            .filter(**prefilter)
            .annotate(
                _wdr_stream_value=Cast(
                    definition.stream_field, output_field=TextField()
                )
            )
            .values_list("pk", "_wdr_stream_value")
        )
        matching_ids = []
        for page_id, stream_value in values.iterator(chunk_size=200):
            if definition.block_path in self._get_present_paths(
                model, definition.stream_field, stream_value
            ):
                matching_ids.append(page_id)
        return scoped_pages.filter(pk__in=matching_ids)


def _parse_filters(
    request: HttpRequest,
) -> tuple[dict[str, str], Optional[int], Optional[int], str]:
    filters = {
        "q": request.GET.get("q", "").strip(),
        "type": request.GET.get("type", "ALL"),
        "site": request.GET.get("site", ""),
        "min_usage": request.GET.get("min_usage", ""),
        "max_usage": request.GET.get("max_usage", ""),
        "definition": request.GET.get("definition", ""),
    }
    try:
        minimum = int(filters["min_usage"]) if filters["min_usage"] else None
        maximum = int(filters["max_usage"]) if filters["max_usage"] else None
        if (
            (minimum is not None and minimum < 0)
            or (maximum is not None and maximum < 0)
            or (minimum is not None and maximum is not None and minimum > maximum)
        ):
            raise ValueError
    except ValueError:
        return filters, None, None, (
            "Usage range must contain non-negative numbers, with min no greater "
            "than max."
        )
    return filters, minimum, maximum, ""


def _definition_matches(
    definition: ComponentDefinition,
    query: str,
    component_type: str,
    definition_id: str = "",
) -> bool:
    if definition_id and definition.definition_id != definition_id:
        return False
    if component_type != "ALL" and definition.component_type != component_type:
        return False
    searchable = " ".join(
        (definition.hierarchy, definition.clean_name, definition.model_label)
    ).casefold()
    return not query or query.casefold() in searchable


def _audit_item(
    definition: ComponentDefinition,
    site: Optional[Site],
    usage: Optional[UsageData] = None,
) -> AuditItem:
    return {
        "definition_id": definition.definition_id,
        "site_id": site.pk if site is not None else None,
        "site_name": WagtailAuditor.site_name(site),
        "hierarchy": definition.hierarchy,
        "clean_name": definition.clean_name,
        "type": definition.component_type,
        "fields": definition.fields,
        "usage": usage or empty_usage(),
        "template": definition.template,
        "template_label": definition.template_label,
    }


@user_passes_test(require_developer_reference_access)
def developer_reference_view(request: HttpRequest) -> HttpResponse:
    applied = request.GET.get("apply") == "1"
    auditor = WagtailAuditor()
    definitions = auditor.definition_catalog()
    filters, minimum, maximum, error = _parse_filters(request)
    site = None
    if filters["site"]:
        site = Site.objects.select_related("root_page").filter(
            pk=filters["site"]
        ).first()
        if site is None:
            error = "The selected site does not exist."
    filtered_definitions: list[ComponentDefinition] = []
    if applied and not error:
        filtered_definitions = [
            item for item in definitions
            if _definition_matches(
                item, filters["q"], filters["type"], filters["definition"]
            )
        ]
    usage_requested = minimum is not None or maximum is not None
    usage_by_definition: dict[str, UsageData] = {}
    if filtered_definitions and usage_requested:
        usage_by_definition = auditor.calculate_usage(filtered_definitions, site)
        filtered_definitions = [
            item for item in filtered_definitions
            if (
                minimum is None
                or usage_by_definition[item.definition_id]["total"] >= minimum
            ) and (
                maximum is None
                or usage_by_definition[item.definition_id]["total"] <= maximum
            )
        ]
    filtered_definitions.sort(
        key=lambda item: (item.hierarchy.casefold(), item.component_type)
    )
    definition_page = Paginator(filtered_definitions, 20).get_page(
        request.GET.get("page")
    )
    definition_page.object_list = [
        _audit_item(item, site, usage_by_definition.get(item.definition_id))
        for item in definition_page.object_list
    ]
    quick_search_items = sorted(
        definitions, key=lambda item: (item.hierarchy.casefold(), item.component_type)
    )[:30]
    return render(request, "index.html", {
        "audit_data": definition_page,
        "page_obj": definition_page,
        "usage_requested": usage_requested,
        "quick_search_items": quick_search_items,
        "sites": Site.objects.select_related("root_page").order_by("site_name", "id"),
        "filters": filters,
        "is_applied": applied,
        "filter_error": error,
    })


@user_passes_test(require_developer_reference_access)
def developer_catalog_search_view(request: HttpRequest) -> JsonResponse:
    query = request.GET.get("q", "").strip()
    component_type = request.GET.get("type", "ALL")
    try:
        limit = max(1, min(int(request.GET.get("limit", "30")), 30))
    except ValueError:
        limit = 30
    matches = sorted(
        (
            item for item in WagtailAuditor.definition_catalog()
            if _definition_matches(item, query, component_type)
        ),
        key=lambda item: (item.hierarchy.casefold(), item.component_type),
    )
    definitions = matches[:limit]
    return JsonResponse({
        "results": [
            {"id": item.definition_id, "type": item.component_type,
             "name": item.hierarchy}
            for item in definitions
        ],
        "limit": limit,
        "total": len(matches),
    })


def _render_usage_detail(
    request: HttpRequest, definition: ComponentDefinition
) -> HttpResponse:
    auditor = WagtailAuditor()
    site_filter = request.GET.get("site", "")
    site = None
    if site_filter:
        site = Site.objects.select_related("root_page").filter(pk=site_filter).first()
    pages = auditor.pages_for_definition(definition, site)
    search_query = request.GET.get("q", "").strip()
    if search_query:
        pages = pages.filter(
            Q(title__icontains=search_query) | Q(slug__icontains=search_query)
        )
    pages = pages.select_related("content_type").only(
        "id", "title", "slug", "live", "url_path", "content_type"
    )
    page_obj = Paginator(
        pages.order_by("title", "pk").distinct(), 50
    ).get_page(request.GET.get("page"))
    return render(request, "detail.html", {
        "component_name": definition.hierarchy,
        "definition": definition,
        "pages": page_obj,
        "page_obj": page_obj,
        "search_query": search_query,
        "site_filter": site_filter,
    })


@user_passes_test(require_developer_reference_access)
def developer_definition_usage_view(
    request: HttpRequest, definition_id: str
) -> HttpResponse:
    definition = next((
        item for item in WagtailAuditor.definition_catalog()
        if item.definition_id == definition_id
    ), None)
    if definition is None:
        return HttpResponse("Unknown component definition", status=404)
    return _render_usage_detail(request, definition)


@user_passes_test(require_developer_reference_access)
def developer_usage_detail_view(
    request: HttpRequest,
    component_type: str,
    component_name: str,
) -> HttpResponse:
    matches = [
        item for item in WagtailAuditor.definition_catalog()
        if item.component_type == component_type and item.clean_name == component_name
    ]
    if len(matches) == 1:
        query = request.GET.urlencode()
        url = reverse("dev_definition_usage", args=(matches[0].definition_id,))
        return redirect(f"{url}?{query}" if query else url)
    params = {"apply": "1", "q": component_name, "type": component_type}
    if request.GET.get("site"):
        params["site"] = request.GET["site"]
    return redirect(f"{reverse('dev_reference')}?{urlencode(params)}")


@hooks.register("register_admin_urls")
def register_admin_urls() -> list[URLPattern]:
    return [
        path("developer-reference/", developer_reference_view, name="dev_reference"),
        path(
            "developer-reference/catalog/", developer_catalog_search_view,
            name="dev_catalog_search",
        ),
        path(
            "developer-reference/definition/<str:definition_id>/usage/",
            developer_definition_usage_view, name="dev_definition_usage",
        ),
        path(
            "developer-reference/<str:component_type>/<str:component_name>/",
            developer_usage_detail_view, name="dev_usage_detail",
        ),
    ]


class DeveloperReferenceMenuItem(MenuItem):
    def is_shown(self, request: HttpRequest) -> bool:
        return user_can_access_developer_reference(request.user)


@hooks.register("register_admin_menu_item")
def register_menu() -> MenuItem:
    return DeveloperReferenceMenuItem(
        "System Registry", reverse("dev_reference"), icon_name="code", order=10000
    )
