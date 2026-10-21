"""Candidate-only endpoints. Ownership comes from the session, never a posted ID."""

from django.contrib import messages
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .access import candidate_required
from .forms import (
    CertificationFormSet,
    EducationFormSet,
    ExperienceFormSet,
    PortfolioFormSet,
    ProfileForm,
    SkillFormSet,
)
from .models import CandidateProfile
from .selectors import profile_for
from matching.skills import standardize_skills

SECTIONS = [
    (
        "skills",
        "Skills",
        "Add one skill per entry. Use the terms you normally use to describe your skills.",
        SkillFormSet,
        "Add skill",
    ),
    (
        "education",
        "Education and qualifications",
        "Include completed qualifications and any studies in progress.",
        EducationFormSet,
        "Add education",
    ),
    (
        "certifications",
        "Certifications",
        "List relevant certifications. Dates and credential links are optional.",
        CertificationFormSet,
        "Add certification",
    ),
    (
        "experience",
        "Work experience",
        "Include employment, internships, freelance work or relevant volunteer experience.",
        ExperienceFormSet,
        "Add experience",
    ),
    (
        "portfolio",
        "Portfolio links",
        "Optional. Link to work samples, projects or a professional website.",
        PortfolioFormSet,
        "Add link",
    ),
]


@candidate_required
def profile(request):
    instance = profile_for(request.user)
    return render(
        request,
        "candidates/profile.html",
        {
            "profile": instance,
            "skill_standardization": standardize_skills(
                [skill.name for skill in instance.skills.all()] if instance else []
            ),
        },
    )


@candidate_required
@require_http_methods(["GET", "POST"])
def profile_edit(request):
    instance = profile_for(request.user) or CandidateProfile(user=request.user)
    data = request.POST if request.method == "POST" else None
    form = ProfileForm(data, instance=instance)
    sections = [
        {
            "prefix": prefix,
            "title": title,
            "description": description,
            "formset": factory(data, instance=instance, prefix=prefix),
            "add_label": add_label,
        }
        for prefix, title, description, factory, add_label in SECTIONS
    ]
    if request.method == "POST":
        # Evaluate every section so users see all errors in one response.
        valid_sections = [section["formset"].is_valid() for section in sections]
        if form.is_valid() and all(valid_sections):
            try:
                with transaction.atomic():
                    saved_profile = form.save()
                    for section in sections:
                        section["formset"].instance = saved_profile
                        section["formset"].save()
            except IntegrityError:
                form.add_error(
                    None,
                    "These changes conflict with saved information. Reload your profile and try again.",
                )
            else:
                messages.success(request, "Your profile has been saved.")
                return redirect("candidates:profile")
    has_errors = form.is_bound and (
        bool(form.errors)
        or any(
            section["formset"].errors or section["formset"].non_form_errors()
            for section in sections
        )
    )
    return render(
        request,
        "candidates/profile_edit.html",
        {
            "form": form,
            "sections": sections,
            "profile": instance,
            "has_errors": has_errors,
        },
    )
