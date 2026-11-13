from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory
from .models import JobPosting, JobSkill
from config.date_fields import configure_future_dates
from django.utils import timezone


class JobPostingForm(forms.ModelForm):
    reopen_applications = forms.BooleanField(
        required=False,
        label="Reopen applications for this job",
        help_text="Only select this if you want to accept applications again. Choose a current or future deadline, or leave it blank.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        configure_future_dates(self, "application_deadline", end=None)
        if self.instance.status != JobPosting.Status.CLOSED:
            self.fields.pop("reopen_applications", None)

    def clean(self):
        data = super().clean()
        deadline = data.get("application_deadline")
        if (
            data.get("reopen_applications")
            and deadline
            and deadline < timezone.localdate()
        ):
            self.add_error(
                "application_deadline",
                "Choose today or a future deadline before reopening applications.",
            )
        return data

    def save(self, commit=True):
        job = super().save(commit=False)
        if self.cleaned_data.get("reopen_applications"):
            job.status = JobPosting.Status.OPEN
        if commit:
            job.save()
            self.save_m2m()
        return job

    class Meta:
        model = JobPosting
        fields = [
            "title",
            "company",
            "location",
            "application_deadline",
            "description",
            "requirements",
            "education_level",
            "education_field",
            "education_priority",
            "minimum_experience_years",
            "experience_details",
            "experience_priority",
        ]
        labels = {
            "requirements": "Additional requirements",
            "education_level": "Minimum qualification",
            "education_field": "Field of study or equivalent qualification",
            "education_priority": "Education priority",
            "minimum_experience_years": "Minimum years of relevant experience",
            "experience_details": "Relevant experience",
            "experience_priority": "Experience priority",
        }
        widgets = {
            "application_deadline": forms.DateInput(
                format="%Y-%m-%d", attrs={"type": "date"}
            ),
            "description": forms.Textarea(attrs={"rows": 3}),
            "requirements": forms.Textarea(attrs={"rows": 2}),
            "experience_details": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "e.g. Building web applications, including internships or freelance work",
                }
            ),
            "education_field": forms.TextInput(
                attrs={"placeholder": "e.g. Computer science or a related field"}
            ),
            "minimum_experience_years": forms.NumberInput(
                attrs={"min": 0, "max": 60, "step": "0.1"}
            ),
        }
        help_texts = {
            "requirements": "Optional. Add certifications, portfolio expectations or other details not covered below.",
            "minimum_experience_years": "Leave blank if there is no minimum, or enter 0 for an entry-level role. Fractions such as 0.5 are allowed.",
            "education_field": "Optional. Describe related subjects or equivalent qualifications you accept.",
        }


class JobSkillForm(forms.ModelForm):
    class Meta:
        model = JobSkill
        fields = ("name", "requirement", "priority")
        labels = {"name": "Skill", "requirement": "Requirement"}
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "placeholder": "e.g. Python — one skill per entry",
                    "list": "skill-suggestions",
                    "data-skill-input": "",
                    "autocomplete": "off",
                }
            )
        }

    def clean_name(self):
        return " ".join(self.cleaned_data["name"].split())


class JobSkillEntryFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        seen = set()
        for form in self.forms:
            entry = form.cleaned_data.get("id")
            # Check ownership even for rows marked for deletion.
            if entry and entry.job_id != self.instance.pk:
                raise ValidationError(
                    "A skill does not belong to this job. Reload the page and try again."
                )
            if form.cleaned_data.get("DELETE"):
                continue
            name = form.cleaned_data.get("name", "").casefold()
            if name and name in seen:
                form.add_error(
                    "name",
                    "This skill is already listed. Keep one entry for each skill.",
                )
                raise ValidationError("Remove duplicate skills before saving.")
            if name:
                seen.add(name)


JobSkillFormSet = inlineformset_factory(
    JobPosting,
    JobSkill,
    form=JobSkillForm,
    fields=JobSkillForm.Meta.fields,
    formset=JobSkillEntryFormSet,
    extra=1,
    can_delete=True,
    max_num=40,
    validate_max=True,
    absolute_max=80,
)
