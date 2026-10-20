"""Application-only copies reuse profile validation without saving profile models."""

from django import forms
from django.forms import BaseFormSet, formset_factory
from candidates.forms import (
    CertificationForm,
    EducationForm,
    ExperienceForm,
    PortfolioForm,
    SkillForm,
)
from candidates.models import CandidateDocument
from .models import Application


class ApplicationForm(forms.Form):
    cover_letter = forms.CharField(
        required=False,
        max_length=4000,
        widget=forms.Textarea(attrs={"rows": 5}),
        label="Message to the recruiter",
    )
    documents = forms.ModelMultipleChoiceField(
        queryset=CandidateDocument.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Attach documents",
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["documents"].queryset = user.documents.all()
        self.fields["documents"].label_from_instance = (
            lambda item: f"{item.get_kind_display()}: {item.title or item.original_name}"
        )

    def clean_documents(self):
        documents = self.cleaned_data["documents"]
        if documents.count() > 10:
            raise forms.ValidationError(
                "Choose up to 10 documents for one application."
            )
        return documents


class UniqueSkillFormSet(BaseFormSet):
    def clean(self):
        super().clean()
        seen = set()
        for form in self.forms:
            if form.cleaned_data.get("DELETE"):
                continue
            name = form.cleaned_data.get("name", "").casefold()
            if name and name in seen:
                form.add_error("name", "This skill is already listed.")
            if name:
                seen.add(name)


def application_formset(form, maximum=30, formset=BaseFormSet):
    return formset_factory(
        form,
        formset=formset,
        extra=1,
        can_delete=True,
        max_num=maximum,
        validate_max=True,
        absolute_max=100,
    )


APPLICATION_SECTIONS = [
    (
        "skills",
        "Skills",
        application_formset(SkillForm, 60, UniqueSkillFormSet),
        "Add skill",
    ),
    (
        "education",
        "Education and qualifications",
        application_formset(EducationForm),
        "Add education",
    ),
    (
        "certifications",
        "Certifications",
        application_formset(CertificationForm),
        "Add certification",
    ),
    (
        "experience",
        "Work experience",
        application_formset(ExperienceForm),
        "Add experience",
    ),
    (
        "portfolio",
        "Portfolio links",
        application_formset(PortfolioForm, 10),
        "Add link",
    ),
]


class ApplicationStatusForm(forms.Form):
    status = forms.ChoiceField(
        choices=[
            choice for choice in Application.Status.choices if choice[0] != "draft"
        ]
    )
