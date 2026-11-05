from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse


class RegistryHelpTests(TestCase):
    def test_min_usage_help_is_available_without_applying_filters(self):
        user = get_user_model().objects.create_superuser(
            username="registry-admin", email="admin@example.com", password="password"
        )
        user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="wagtail_developer_reference",
                codename="access_developer_reference",
            )
        )
        self.client.force_login(user)

        response = self.client.get(reverse("dev_reference"))

        self.assertContains(response, '<label for="min-usage">Min usage</label>')
        self.assertContains(
            response,
            '<button id="min-usage-help" class="usage-help-icon" type="button" '
            'aria-label="About Min usage" aria-describedby="min-usage-tooltip">'
            '<span aria-hidden="true">i</span></button>',
            html=True,
        )
        self.assertContains(
            response,
            '<span id="min-usage-tooltip" class="usage-help-tooltip" role="tooltip">'
            "Usage counts for pages, blocks, images and documents are only shown "
            "when Min usage is filled in. Enter 0 to include items with no usage, "
            "then apply the filters.</span>",
            html=True,
        )
