from django import forms
from .models import JobPosting


class JobPostingForm(forms.ModelForm):
    class Meta:
        model = JobPosting
        fields = ["title", "company", "location", "description", "requirements"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
            "requirements": forms.Textarea(attrs={"rows": 5}),
        }
        help_texts = {
            "requirements": "Describe the skills, qualifications and experience needed for this role."
        }
