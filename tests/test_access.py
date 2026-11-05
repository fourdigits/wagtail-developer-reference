from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, Permission, User
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings

from wagtail_developer_reference.wagtail_hooks import (
    developer_reference_view,
    developer_usage_detail_view,
)


class DeveloperReferenceAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create(username="superuser", is_superuser=True)
        cls.admin_user = User.objects.create(username="admin")
        cls.regular_user = User.objects.create(username="regular")
        cls.staff_user = User.objects.create(username="staff", is_staff=True)
        cls.inactive_user = User.objects.create(username="inactive", is_active=False)
        permission = Permission.objects.get(
            content_type__app_label="wagtailadmin", codename="access_admin"
        )
        cls.admin_user.user_permissions.add(permission)
        cls.inactive_user.user_permissions.add(permission)

    def test_access_to_registry_and_usage_details(self):
        setting_name = "WAGTAIL_DEVELOPER_REFERENCE_ALLOW_ALL_ADMIN_USERS"
        users = [
            self.superuser,
            self.admin_user,
            self.regular_user,
            self.staff_user,
            self.inactive_user,
            AnonymousUser(),
        ]
        views = [
            (developer_reference_view, ()),
            (developer_usage_detail_view, ("PAGE", "Page")),
        ]

        with (
            patch(
                "wagtail_developer_reference.wagtail_hooks.WagtailAuditor"
            ) as auditor,
            patch(
                "wagtail_developer_reference.wagtail_hooks.get_page_models",
                return_value=[],
            ),
            patch(
                "wagtail_developer_reference.wagtail_hooks.render",
                return_value=HttpResponse("Developer Reference"),
            ),
        ):
            auditor.return_value.run.return_value = []
            for setting_overrides in ({}, {setting_name: False}, {setting_name: True}):
                with override_settings(**setting_overrides):
                    for user in users:
                        allowed = user.is_superuser or (
                            setting_overrides.get(setting_name, False)
                            and user == self.admin_user
                        )
                        for view, arguments in views:
                            with self.subTest(
                                setting=setting_overrides,
                                user=str(user),
                                view=view.__name__,
                            ):
                                request = RequestFactory().get(
                                    "/admin/developer-reference/"
                                )
                                request.user = user
                                if allowed:
                                    self.assertEqual(
                                        view(request, *arguments).status_code, 200
                                    )
                                else:
                                    with self.assertRaises(PermissionDenied):
                                        view(request, *arguments)
