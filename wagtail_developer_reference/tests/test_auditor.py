from django.test import SimpleTestCase, TestCase
from wagtail.blocks import CharBlock, StreamBlock, StructBlock
from wagtail.models import Page, Site

from wagtail_developer_reference.wagtail_hooks import WagtailAuditor


class TimelineBlock(StructBlock):
    title = CharBlock(required=False)
    content = StreamBlock(
        [
            ("logo", CharBlock(required=False)),
            ("image", CharBlock(required=False)),
        ],
        required=False,
    )


class DefinitionPathTests(SimpleTestCase):
    def setUp(self):
        self.auditor = object.__new__(WagtailAuditor)
        self.root_block = StreamBlock([("timeline", TimelineBlock())])

    def test_raw_nested_stream_paths_are_exact_and_unique(self):
        value = [
            {
                "type": "timeline",
                "value": {
                    "title": "First",
                    "content": [
                        {"type": "logo", "value": "A"},
                        {"type": "image", "value": "B"},
                        {"type": "image", "value": "C"},
                    ],
                },
            }
        ]
        present = set()

        self.auditor._collect_present_paths(self.root_block, value, (), present)

        self.assertIn(("timeline",), present)
        self.assertIn(("timeline", "title"), present)
        self.assertIn(("timeline", "content", "logo"), present)
        self.assertIn(("timeline", "content", "image"), present)
        self.assertEqual(
            len([path for path in present if path[-1] == "image"]), 1
        )

    def test_definition_id_includes_model_field_and_path(self):
        first = WagtailAuditor._definition_id(
            "BLOCK", "demo.articlepage", "body", ("timeline", "title")
        )
        same = WagtailAuditor._definition_id(
            "BLOCK", "demo.articlepage", "body", ("timeline", "title")
        )
        other = WagtailAuditor._definition_id(
            "BLOCK", "demo.homepage", "body", ("timeline", "title")
        )

        self.assertEqual(first, same)
        self.assertNotEqual(first, other)


class SiteScopeTests(TestCase):
    def test_site_root_is_included_and_nested_site_is_excluded(self):
        tree_root = Page.get_first_root_node()
        site_root = tree_root.add_child(
            instance=Page(title="Package test site", slug="package-test-site")
        )
        included_child = site_root.add_child(
            instance=Page(title="Included", slug="included")
        )
        nested_root = site_root.add_child(
            instance=Page(title="Nested site", slug="nested-site")
        )
        nested_child = nested_root.add_child(
            instance=Page(title="Nested child", slug="nested-child")
        )
        site = Site.objects.create(
            hostname="package-test.example",
            port=8123,
            root_page=site_root,
        )
        Site.objects.create(
            hostname="nested-package-test.example",
            port=8124,
            root_page=nested_root,
        )

        page_ids = set(
            WagtailAuditor()._scope_page_queryset(site).values_list(
                "pk", flat=True
            )
        )

        self.assertIn(site_root.pk, page_ids)
        self.assertIn(included_child.pk, page_ids)
        self.assertNotIn(nested_root.pk, page_ids)
        self.assertNotIn(nested_child.pk, page_ids)
