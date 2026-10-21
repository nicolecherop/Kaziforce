from django.contrib import admin
from config.admin import ReadOnlyAdmin
from .models import (
    CatalogueSkill,
    SkillCatalogue,
    MatchingCorpus,
    MatchRun,
    MatchResult,
)


class ReferenceAdmin(ReadOnlyAdmin):
    """Catalogue content changes only through the versioned import command."""


@admin.register(SkillCatalogue)
class SkillCatalogueAdmin(ReferenceAdmin):
    list_display = ["version", "language", "skill_count", "active", "imported_at"]


@admin.register(CatalogueSkill)
class CatalogueSkillAdmin(ReferenceAdmin):
    list_display = ["preferred_label", "catalogue"]
    list_filter = ["catalogue"]
    search_fields = ["preferred_label", "uri"]


@admin.register(MatchingCorpus)
class MatchingCorpusAdmin(ReadOnlyAdmin):
    list_display = ("catalogue", "tokenizer_version", "document_count", "created_at")
    search_fields = ("checksum", "source_checksum")
    exclude = ("document_frequencies",)


@admin.register(MatchRun)
class MatchRunAdmin(ReadOnlyAdmin):
    list_display = ("id", "kind", "owner", "job", "created_at")
    list_filter = ("kind",)
    search_fields = ("owner__email", "job__title", "input_checksum")
    list_select_related = ("owner", "job", "corpus")
    date_hierarchy = "created_at"


@admin.register(MatchResult)
class MatchResultAdmin(ReadOnlyAdmin):
    list_display = ("id", "candidate", "job", "score", "rank")
    search_fields = ("candidate__email", "job__title", "input_checksum")
    list_select_related = ("candidate", "job", "application", "run")
