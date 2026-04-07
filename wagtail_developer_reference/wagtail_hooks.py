import inspect

from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.template.loader import get_template
from django.urls import path
from django.urls import reverse
from wagtail import hooks
from wagtail.admin.menu import MenuItem
from wagtail.blocks import StructBlock
from wagtail.fields import StreamField
from wagtail.models import Site, get_page_models


def is_superuser(user):
    if user.is_superuser:
        return True
    raise PermissionDenied


class WagtailAuditor:
    def __init__(self):
        self.results = []
        self.seen_blocks = set()
        self.all_page_models = get_page_models()
        self.sites = Site.objects.all()
        self.models_with_streamfields = [
            model for model in self.all_page_models
            if any(isinstance(field, StreamField) for field in model._meta.get_fields())
        ]
        self.excluded_fields = {
            "path", "depth", "numchild", "content_type", "page_ptr",
            "go_live_at", "expire_at", "show_in_menus", "first_published_at",
            "last_published_at", "latest_revision_created_at",
        }

    def get_template_path(self, template_name):
        if not template_name:
            return "Default Rendering"
        try:
            return get_template(template_name).origin.name
        except Exception:
            return "Template not found"

    def _analyze_model_field(self, field):
        if field.name in self.excluded_fields:
            return None, None
        if not field.is_relation or field.many_to_one:
            label = getattr(field, "verbose_name", field.name)
            if hasattr(label, "__str__"):
                label = str(label).capitalize()
            field_type = type(field).__name__
            is_structure = "StreamField" in field_type or "RichTextField" in field_type
            category = "structure" if is_structure else "metadata"
            return f"{label} ({field_type})", category
        return None, None

    def get_internal_structure(self, object_instance):
        structure_fields = []
        metadata_fields = []

        if hasattr(object_instance, "child_blocks"):
            for name, block in object_instance.child_blocks.items():
                label = getattr(block.meta, "label", name)
                structure_fields.append(f"{label} ({type(block).__name__})")
        elif hasattr(object_instance, "_meta"):
            for field in object_instance._meta.get_fields():
                info, category = self._analyze_model_field(field)
                if category == "structure":
                    structure_fields.append(info)
                elif category == "metadata":
                    metadata_fields.append(info)

        return {"structure": structure_fields, "metadata": metadata_fields}

    def _get_usage_for_site(self, model, site, block_name=None):
        queryset = model.objects.descendant_of(site.root_page)
        if block_name:
            search_key = f'"{block_name}"'
            fields = model._meta.get_fields()
            stream_fields = [f.name for f in fields if isinstance(f, StreamField)]
            total_count = 0
            live_count = 0
            for field_name in stream_fields:
                total_count += queryset.filter(**{f"{field_name}__icontains": search_key}).count()
                live_count += queryset.live().filter(**{f"{field_name}__icontains": search_key}).count()
        else:
            total_count = queryset.count()
            live_count = queryset.live().count()
        return {"live": live_count, "total": total_count, "draft": total_count - live_count}

    def process_block(self, block_name, block_object, parent_label, site):
        is_class = inspect.isclass(block_object)
        block_class = block_object.__name__ if is_class else block_object.__class__.__name__
        signature = f"{site.id}_{block_class}_{block_name}"
        if signature in self.seen_blocks:
            return

        site_usage = {"live": 0, "total": 0, "draft": 0}
        for model in self.models_with_streamfields:
            usage_data = self._get_usage_for_site(model, site, block_name)
            site_usage["live"] += usage_data["live"]
            site_usage["total"] += usage_data["total"]
            site_usage["draft"] += usage_data["draft"]

        self.results.append({
            "site_name": str(site),
            "hierarchy": f"{parent_label} → {str(getattr(block_object.meta, 'label', block_name))}",
            "clean_name": block_name,
            "type": "BLOCK",
            "fields": self.get_internal_structure(block_object),
            "usage": site_usage,
            "template": self.get_template_path(getattr(block_object.meta, "template", None)),
        })
        self.seen_blocks.add(signature)

        if isinstance(block_object, StructBlock):
            for child_name, child_object in block_object.child_blocks.items():
                self.process_block(child_name, child_object, parent_label, site)

    def run(self):
        for site in self.sites:
            for model in self.all_page_models:
                usage_data = self._get_usage_for_site(model, site)
                default_tpl = f"{model._meta.app_label}/{model._meta.model_name}.html"
                self.results.append({
                    "site_name": str(site),
                    "hierarchy": str(model._meta.verbose_name).title(),
                    "clean_name": model.__name__,
                    "type": "PAGE",
                    "fields": self.get_internal_structure(model),
                    "usage": usage_data,
                    "template": self.get_template_path(getattr(model, "template", default_tpl)),
                })
                for field in model._meta.get_fields():
                    if isinstance(field, StreamField):
                        for block_name, block_object in field.stream_block.child_blocks.items():
                            self.process_block(block_name, block_object, str(model._meta.verbose_name).title(), site)
        return self.results


@user_passes_test(is_superuser)
def developer_reference_view(request):
    auditor = WagtailAuditor()
    audit_results = auditor.run()
    sorted_results = sorted(audit_results, key=lambda item: (item["site_name"], item["hierarchy"]))
    return render(request, "index.html", {"audit_data": sorted_results})


@user_passes_test(is_superuser)
def developer_usage_detail_view(request, component_type, component_name):
    site_filter_name = request.GET.get('site')
    found_pages = []
    if component_type == "PAGE":
        target_model = next((model for model in get_page_models() if model.__name__ == component_name), None)
        if target_model:
            found_pages = target_model.objects.all()
    else:
        search_key = f'"{component_name}"'
        for model in get_page_models():
            stream_fields = [f.name for f in model._meta.get_fields() if isinstance(f, StreamField)]
            for field_name in stream_fields:
                found_pages.extend(list(model.objects.filter(**{f"{field_name}__icontains": search_key})))

    if site_filter_name:
        found_pages = [page for page in found_pages if str(page.get_site()) == site_filter_name]

    unique_pages = {page.id: page for page in found_pages}.values()
    return render(request, "detail.html", {
        "component_name": component_name,
        "pages": unique_pages
    })


@hooks.register("register_admin_urls")
def register_admin_urls():
    return [
        path("developer-reference/", developer_reference_view, name="dev_reference"),
        path("developer-reference/<str:component_type>/<str:component_name>/", developer_usage_detail_view, name="dev_usage_detail"),
    ]


@hooks.register("register_admin_menu_item")
def register_menu():
    url = reverse("dev_reference")
    return MenuItem("System Registry", url, icon_name="code", order=10000)
