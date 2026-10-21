from django.contrib import admin
from .models import CatalogueSkill, SkillCatalogue


class ReferenceAdmin(admin.ModelAdmin):
    """Catalogue content changes only through the versioned import command."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SkillCatalogue)
class SkillCatalogueAdmin(ReferenceAdmin):
    list_display = ["version", "language", "skill_count", "active", "imported_at"]


@admin.register(CatalogueSkill)
class CatalogueSkillAdmin(ReferenceAdmin):
    list_display = ["preferred_label", "catalogue"]
    list_filter = ["catalogue"]
    search_fields = ["preferred_label", "uri"]
