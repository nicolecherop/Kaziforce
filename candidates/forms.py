"""Profile forms and bounded, owner-scoped groups of repeatable entries."""

from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory

from .models import (
    CandidateProfile,
    CandidateSkill,
    Certification,
    Education,
    PortfolioLink,
    WorkExperience,
)


class ProfileForm(forms.ModelForm):
    class Meta:
        model = CandidateProfile
        fields = ["headline", "location", "summary", "contact_email", "phone_number"]
        labels = {
            "headline": "Professional headline",
            "location": "Location",
            "summary": "Professional summary",
            "contact_email": "Contact email",
            "phone_number": "Phone number",
        }
        help_texts = {
            "headline": "A short description of what you do or the work you are looking for.",
            "location": "Optional. Your city or country; a full address is not needed.",
            "summary": "Describe your experience, interests and the skills you bring. Up to 3,000 characters.",
            "contact_email": "Optional. Use a different email for recruitment, or leave blank to use your account email when applying.",
            "phone_number": "Optional. Include your country code, for example +254 712 345 678. Shared only with applications you submit.",
        }
        widgets = {
            "phone_number": forms.TextInput(
                attrs={"type": "tel", "autocomplete": "tel"}
            ),
            "headline": forms.TextInput(
                attrs={"placeholder": "e.g. Junior software developer"}
            ),
            "location": forms.TextInput(attrs={"placeholder": "e.g. Nairobi, Kenya"}),
            "summary": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": "Introduce yourself and your professional interests...",
                }
            ),
        }

    @property
    def professional_fields(self):
        return [self[name] for name in ("headline", "location", "summary")]

    @property
    def contact_fields(self):
        return [self[name] for name in ("contact_email", "phone_number")]


class SkillForm(forms.ModelForm):
    class Meta:
        model = CandidateSkill
        fields = ["name"]
        labels = {"name": "Skill"}
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "placeholder": "e.g. Python, one skill per entry",
                    "list": "skill-suggestions",
                    "data-skill-input": "",
                    "autocomplete": "off",
                }
            )
        }

    def clean_name(self):
        return " ".join(self.cleaned_data["name"].split())


class EducationForm(forms.ModelForm):
    class Meta:
        model = Education
        fields = [
            "qualification",
            "institution",
            "field_of_study",
            "start_date",
            "end_date",
            "currently_studying",
        ]
        labels = {"currently_studying": "I am currently studying here"}
        widgets = {
            name: forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})
            for name in ["start_date", "end_date"]
        }


class CertificationForm(forms.ModelForm):
    class Meta:
        model = Certification
        fields = [
            "name",
            "issuer",
            "issue_date",
            "expiry_date",
            "credential_id",
            "credential_url",
        ]
        labels = {
            "name": "Certification name",
            "issuer": "Issuing organisation",
            "credential_url": "Credential link",
        }
        widgets = {
            name: forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})
            for name in ["issue_date", "expiry_date"]
        }


class ExperienceForm(forms.ModelForm):
    class Meta:
        model = WorkExperience
        fields = [
            "job_title",
            "company",
            "start_date",
            "end_date",
            "currently_working",
            "description",
        ]
        labels = {
            "currently_working": "I currently work here",
            "description": "Responsibilities and achievements",
        }
        widgets = {
            "start_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "end_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class PortfolioForm(forms.ModelForm):
    class Meta:
        model = PortfolioLink
        fields = ["title", "url"]
        labels = {"title": "Link title", "url": "Web address"}
        widgets = {
            "title": forms.TextInput(
                attrs={"placeholder": "e.g. GitHub or personal website"}
            )
        }


class OwnedEntryFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        for form in self.forms:
            entry = form.cleaned_data.get("id")
            if entry and entry.profile_id != self.instance.pk:
                raise ValidationError(
                    "An entry does not belong to your profile. Reload the page and try again."
                )


class SkillEntryFormSet(OwnedEntryFormSet):
    def clean(self):
        super().clean()
        seen = set()
        for form in self.forms:
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


def entry_formset(model, form, maximum=30, formset=OwnedEntryFormSet):
    return inlineformset_factory(
        CandidateProfile,
        model,
        form=form,
        fields=tuple(form._meta.fields),
        formset=formset,
        extra=1,
        can_delete=True,
        max_num=maximum,
        validate_max=True,
        absolute_max=100,
    )


SkillFormSet = entry_formset(
    CandidateSkill, SkillForm, maximum=60, formset=SkillEntryFormSet
)
EducationFormSet = entry_formset(Education, EducationForm)
CertificationFormSet = entry_formset(Certification, CertificationForm)
ExperienceFormSet = entry_formset(WorkExperience, ExperienceForm)
PortfolioFormSet = entry_formset(PortfolioLink, PortfolioForm, maximum=10)
