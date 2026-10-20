from django.contrib import admin
from .models import JobPosting


@admin.register(JobPosting)
class JobPostingAdmin(admin.ModelAdmin):
    list_display = ["title", "company", "recruiter", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["title", "company", "recruiter__email"]
