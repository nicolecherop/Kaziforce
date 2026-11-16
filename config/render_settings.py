"""Settings for the temporary hosted demonstration."""

import os

import dj_database_url

from .settings import *

DEBUG = False
SITE_URL = os.environ["RENDER_EXTERNAL_URL"]
ALLOWED_HOSTS = [os.environ["RENDER_EXTERNAL_HOSTNAME"]]
CSRF_TRUSTED_ORIGINS = [SITE_URL]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
DATABASES = {"default": dj_database_url.parse(os.environ["DATABASE_URL"])}
MIDDLEWARE = [MIDDLEWARE[0], "whitenoise.middleware.WhiteNoiseMiddleware", *MIDDLEWARE[1:]]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
PRIVATE_DOCUMENTS_IN_DATABASE = True
EMAIL_BACKEND = "accounts.brevo.EmailBackend"
BREVO_API_KEY = os.environ["BREVO_API_KEY"]
DEFAULT_FROM_EMAIL = os.environ["DEFAULT_FROM_EMAIL"]
EMAIL_TWO_STEP_ENABLED = True
