SECRET_KEY = "developer-reference-tests"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "wagtail",
    "wagtail.admin",
    "wagtail.users",
    "wagtail.documents",
    "wagtail.images",
    "taggit",
    "modelcluster",
    "wagtail_developer_reference",
]

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
STATIC_URL = "/static/"
USE_TZ = True
WAGTAILADMIN_BASE_URL = "http://testserver"
WAGTAIL_SITE_NAME = "Developer Reference tests"
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
