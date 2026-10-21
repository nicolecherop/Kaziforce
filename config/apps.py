"""Use the branded admin site while preserving Django's standard permissions."""

from django.contrib.admin.apps import AdminConfig


class KaziForceAdminConfig(AdminConfig):
    default_site = "config.admin.KaziForceAdminSite"
