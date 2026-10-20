from django.contrib import admin
from .forms import JobSkillEntryFormSet, JobSkillForm
from .models import JobPosting, JobSkill


class JobSkillInline(admin.TabularInline):
    model = JobSkill
    form = JobSkillForm
    formset = JobSkillEntryFormSet
    extra = 0
    max_num = 40


@admin.register(JobPosting)
class JobPostingAdmin(admin.ModelAdmin):
    list_display = ["title", "company", "recruiter", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["title", "company", "recruiter__email"]
    inlines = [JobSkillInline]
