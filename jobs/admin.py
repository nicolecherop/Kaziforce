from django.contrib import admin
from django import forms
from django.utils import timezone
from .forms import JobSkillEntryFormSet, JobSkillForm
from .models import JobPosting, JobSkill


class ApplicationAvailabilityFilter(admin.SimpleListFilter):
    title = "Application availability"
    parameter_name = "application_window"

    def lookups(self, request, model_admin):
        return [
            ("open", "Accepting applications"),
            ("expired", "Deadline passed"),
            ("closed", "Manually closed"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "open":
            return queryset.accepting_applications()
        if self.value() == "expired":
            return queryset.filter(
                status="open", application_deadline__lt=timezone.localdate()
            )
        if self.value() == "closed":
            return queryset.filter(status="closed")
        return queryset


class JobSkillInline(admin.TabularInline):
    model = JobSkill
    form = JobSkillForm
    formset = JobSkillEntryFormSet
    extra = 0
    max_num = 40


@admin.register(JobPosting)
class JobPostingAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "company",
        "recruiter",
        "application_status",
        "application_deadline",
        "created_at",
    ]
    list_filter = [ApplicationAvailabilityFilter, "application_deadline"]
    date_hierarchy = "created_at"
    search_fields = ["title", "company", "recruiter__email"]
    inlines = [JobSkillInline]

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "application_deadline":
            kwargs["widget"] = forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date", "min": timezone.localdate().isoformat()},
            )
        return super().formfield_for_dbfield(db_field, request, **kwargs)
