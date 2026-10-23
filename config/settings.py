"""Environment-based Django configuration for local development and deployment."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    raise RuntimeError("Set DJANGO_SECRET_KEY in .env before starting KaziForce.")
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
INSTALLED_APPS = [
    "config.apps.KaziForceAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "candidates",
    "jobs",
    "applications",
    "matching",
    "pages",
    "freelance",
    "mpesa",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "accounts.security_middleware.VerifiedSessionMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
if os.getenv("DATABASE_ENGINE", "postgresql") == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB", "kaziforce"),
            "USER": os.getenv("POSTGRES_USER", "kaziforce_app"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
            "HOST": os.getenv("POSTGRES_HOST", "localhost"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
            "TEST": {"NAME": os.getenv("POSTGRES_TEST_DB", "test_kaziforce")},
        }
    }
AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
# Do not map this directory into a public web-server/media route.
PRIVATE_DOCUMENT_ROOT = BASE_DIR / "private_uploads"
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "accounts:sign_in"
LOGIN_REDIRECT_URL = "accounts:dashboard"
LOGOUT_REDIRECT_URL = "pages:home"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
EMAIL_BACKEND = os.getenv(
    "DJANGO_EMAIL_BACKEND",
    (
        "django.core.mail.backends.console.EmailBackend"
        if DEBUG
        else "django.core.mail.backends.smtp.EmailBackend"
    ),
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "KaziForce <noreply@localhost>")

# Candidate display threshold; this does not change scores or recruiter rankings.
MATCH_RECOMMENDATION_MIN_SCORE = 60

# Google identity uses only basic profile/email scopes, never Gmail/Calendar access.
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
ACCOUNT_ADAPTER = "accounts.auth_adapters.AccountAdapter"
SOCIALACCOUNT_ADAPTER = "accounts.auth_adapters.GoogleAccountAdapter"
SOCIALACCOUNT_FORMS = {"signup": "accounts.social_forms.GoogleSignupForm"}
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_LOGIN_BY_CODE_ENABLED = (
    False  # No email-only route around password verification.
)
ACCOUNT_LOGIN_BY_CODE_TIMEOUT = 300
ACCOUNT_LOGIN_BY_CODE_MAX_ATTEMPTS = 5
ACCOUNT_LOGIN_BY_CODE_SUPPORTS_RESEND = 3
ACCOUNT_LOGIN_BY_CODE_TRUST_ENABLED = False
ACCOUNT_LOGIN_TIMEOUT = 600
ACCOUNT_LOGIN_BY_CODE_FORMAT = {"length": 6, "numeric": True, "dashed": False}
ACCOUNT_SESSION_REMEMBER = False
SOCIALACCOUNT_AUTO_SIGNUP = False
SOCIALACCOUNT_EMAIL_AUTHENTICATION = False
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = False
SOCIALACCOUNT_LOGIN_ON_GET = False
SOCIALACCOUNT_STORE_TOKENS = False
ACCOUNT_LOGOUT_ON_GET = False
ACCOUNT_SIGNUP_REDIRECT_URL = LOGIN_REDIRECT_URL
ACCOUNT_RATE_LIMITS = {
    "login": "20/m/ip,10/m/key",
    "login_failed": "5/5m/key,20/5m/ip",
    "confirm_login_code": "10/m/ip,5/m/key",
}
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_SIGNIN_ENABLED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APPS": (
            [{"client_id": GOOGLE_CLIENT_ID, "secret": GOOGLE_CLIENT_SECRET, "key": ""}]
            if GOOGLE_SIGNIN_ENABLED
            else []
        ),
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online", "prompt": "select_account"},
        "OAUTH_PKCE_ENABLED": True,
    }
}
# Activation is explicit: never require inbox codes while SMTP is unconfigured.
EMAIL_TWO_STEP_ENABLED = os.getenv("EMAIL_TWO_STEP_ENABLED", "false").lower() == "true"
EMAIL_TIMEOUT = 15
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "security_rate_limits",
        "OPTIONS": {"MAX_ENTRIES": 10000},
    }
}
TEMPLATES[0]["OPTIONS"]["context_processors"].append(
    "accounts.auth_context.auth_options"
)


# Sandbox-only integration. No production host, payouts or live-mode switch exists.
MPESA_SANDBOX = {
    "enabled": os.getenv("MPESA_SANDBOX_ENABLED", "false").lower() == "true",
    "consumer_key": os.getenv("MPESA_CONSUMER_KEY", ""),
    "consumer_secret": os.getenv("MPESA_CONSUMER_SECRET", ""),
    "shortcode": os.getenv("MPESA_SANDBOX_SHORTCODE", ""),
    "passkey": os.getenv("MPESA_SANDBOX_PASSKEY", ""),
    "callback_url": os.getenv("MPESA_SANDBOX_CALLBACK_URL", ""),
}
ACCOUNT_RATE_LIMITS["mpesa_sandbox"] = "10/m/key,30/m/ip"
