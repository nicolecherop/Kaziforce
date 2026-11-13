"""Editable CV suggestions with explicit inclusion controls."""

from django import forms
from django.forms import formset_factory
from django.forms.utils import ErrorDict

from .forms import (
    CertificationForm,
    EducationForm,
    ExperienceForm,
    PortfolioForm,
    ProfileForm,
    SkillForm,
)


class ImportProfileForm(ProfileForm):
    selected_fields = forms.MultipleChoiceField(
        label="Details to use",
        required=False,
        choices=[
            (name, ProfileForm._meta.labels[name]) for name in ProfileForm._meta.fields
        ],
        widget=forms.CheckboxSelectMultiple,
        help_text="Only checked details replace the corresponding profile fields. Existing non-empty fields are unchecked initially.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ignore unselected suggestions before model validation. A malformed
        # extracted phone/email must not stop saving other selected sections.
        if self.is_bound:
            self.data = self.data.copy()
            selected = (
                self.data.getlist("selected_fields")
                if hasattr(self.data, "getlist")
                else self.data.get("selected_fields", [])
            )
            for field in self._meta.fields:
                if field not in selected:
                    self.data[field] = ""


def review_form(base):
    class ReviewEntry(base):
        include = forms.BooleanField(
            label="Add this entry to my profile", required=False, initial=True
        )

        def full_clean(self):
            if self.is_bound and not self.fields["include"].to_python(
                self.data.get(self.add_prefix("include"))
            ):
                self._errors = ErrorDict()
                self.cleaned_data = {"include": False}
                return
            super().full_clean()

    return ReviewEntry


IMPORT_SECTIONS = [
    ("skills", "Skills", SkillForm, 60),
    ("education", "Education", EducationForm, 30),
    ("experience", "Work experience", ExperienceForm, 30),
    ("certifications", "Certifications", CertificationForm, 30),
    ("portfolio", "Portfolio links", PortfolioForm, 10),
]


def review_formset(base, maximum):
    return formset_factory(
        review_form(base),
        extra=0,
        max_num=maximum,
        absolute_max=maximum,
        validate_max=True,
    )
