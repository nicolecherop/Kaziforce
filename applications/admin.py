"""Read-only oversight; recruitment changes remain in recruiter workflows."""

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils.html import format_html
from django.views.decorators.http import require_GET

from candidates.document_views import document_response
from config.admin import ReadOnlyAdmin
from pages.presentation import public_text, contact_email
from .models import Application, ApplicationAttachment, Interview, InterviewEmail


class AttachmentInline(admin.TabularInline):
    model = ApplicationAttachment
    fields = ("original_name", "title", "kind")
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Application)
class ApplicationAdmin(ReadOnlyAdmin):
    list_display = ("candidate_label", "job_label", "status", "submitted_at")
    list_filter = ("status",)
    search_fields = ("candidate_name", "candidate_email", "job__title", "job__company")
    list_select_related = ("job",)
    date_hierarchy = "submitted_at"
    exclude = ("documents",)
    inlines = (AttachmentInline,)

    def get_queryset(self, request):
        return super().get_queryset(request).exclude(status="draft")

    @admin.display(description="Candidate")
    def candidate_label(self, obj):
        return public_text(obj.candidate_name) or "Candidate"

    @admin.display(description="Job")
    def job_label(self, obj):
        return public_text(obj.job_snapshot.get("title") or obj.job.title)


@admin.register(ApplicationAttachment)
class ApplicationAttachmentAdmin(ReadOnlyAdmin):
    fields = ("application", "original_name", "title", "kind", "protected_download")
    readonly_fields = ("protected_download",)
    list_display = ("original_name", "kind", "application")
    list_filter = ("kind",)
    search_fields = (
        "original_name",
        "title",
        "application__candidate_name",
        "application__job__title",
    )
    list_select_related = ("application",)

    def get_queryset(self, request):
        return super().get_queryset(request).exclude(application__status="draft")

    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj) and request.user.has_perm(
            "applications.view_application"
        )

    @admin.display(description="Submitted document")
    def protected_download(self, obj):
        return format_html(
            '<a href="{}">Download submitted document</a>',
            reverse("admin:applications_applicationattachment_download", args=[obj.pk]),
        )

    def get_urls(self):
        return [
            path(
                "<uuid:attachment_id>/download/",
                self.admin_site.admin_view(require_GET(self.download)),
                name="applications_applicationattachment_download",
            )
        ] + super().get_urls()

    def download(self, request, attachment_id):
        attachment = get_object_or_404(self.get_queryset(request), pk=attachment_id)
        if not self.has_view_permission(request, attachment):
            raise PermissionDenied
        return document_response(
            attachment.file, attachment.original_name, inline=False
        )


@admin.register(Interview)
class InterviewAdmin(ReadOnlyAdmin):
    list_display = ("job_label", "candidate_label", "starts_at", "format", "status")
    list_filter = ("status", "format")
    search_fields = (
        "application__candidate_name",
        "application__job__title",
        "application__job__company",
        "recruiter_name",
        "recruiter_email",
    )
    list_select_related = ("application__job",)
    date_hierarchy = "starts_at"

    def get_queryset(self, request):
        return super().get_queryset(request).exclude(application__status="draft")

    @admin.display(description="Job")
    def job_label(self, obj):
        return public_text(obj.application.job.title)

    @admin.display(description="Candidate")
    def candidate_label(self, obj):
        return public_text(obj.application.candidate_name) or "Candidate"


@admin.register(InterviewEmail)
class InterviewEmailAdmin(ReadOnlyAdmin):
    list_display = (
        "subject_label",
        "recipient_label",
        "status",
        "attempts",
        "created_at",
        "sent_at",
    )
    list_filter = ("status",)
    search_fields = (
        "subject",
        "recipient_email",
        "interview__application__candidate_name",
        "interview__application__job__title",
    )
    date_hierarchy = "created_at"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .exclude(interview__application__status="draft")
        )

    @admin.display(description="Subject")
    def subject_label(self, obj):
        return public_text(obj.subject)

    @admin.display(description="Recipient")
    def recipient_label(self, obj):
        return contact_email(obj.recipient_email) or "No recruitment contact email"
