"""Candidate-owned CV import: upload, review, then explicitly save."""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from .access import candidate_required
from .cv_forms import IMPORT_SECTIONS, ImportProfileForm, review_formset
from .cv_import import (
    draft_key,
    entry_identity,
    existing_identities,
    new_draft,
    profile_version,
    RELATIONS,
)
from .cv_text import CVReadError
from .models import CandidateDocument, CandidateProfile
from .selectors import profile_for


@candidate_required
@never_cache
@require_POST
def start_import(request, document_id):
    document = get_object_or_404(
        CandidateDocument,
        pk=document_id,
        user=request.user,
        kind=CandidateDocument.Kind.CV,
    )
    if not cache.add(f"cv-import-cooldown:{request.user.pk}", True, 30):
        messages.error(request, "Please wait 30 seconds before reading another CV.")
        return redirect("candidates:documents")
    try:
        token = new_draft(request.user, document)
    except CVReadError as error:
        messages.error(request, str(error))
        return redirect("candidates:documents")
    return redirect("candidates:cv_review", token=token)


def missing_draft(request):
    messages.info(
        request,
        "This CV review has ended or expired. Choose Fill profile from CV to start again.",
    )
    return redirect("candidates:documents")


def review_context(request, draft, data=None):
    profile = profile_for(request.user)
    suggested = draft["suggestions"]
    basic = suggested["basic"]
    selected = [
        name
        for name, value in basic.items()
        if value and not (profile and getattr(profile, name))
    ]
    form = ImportProfileForm(data, initial={**basic, "selected_fields": selected})
    sections = []
    for prefix, title, base, maximum in IMPORT_SECTIONS:
        existing = existing_identities(profile, prefix)
        initial = [
            entry
            for entry in suggested[prefix]
            if entry_identity(prefix, entry) not in existing
        ]
        sections.append(
            {
                "prefix": prefix,
                "title": title,
                "formset": review_formset(base, maximum)(
                    data, initial=initial, prefix=prefix
                ),
                "maximum": maximum,
            }
        )
    return {
        "form": form,
        "sections": sections,
        "draft": draft,
        "current_profile": profile,
    }


@candidate_required
@never_cache
@require_GET
def review_import(request, token):
    draft = cache.get(draft_key(request.user, token))
    if (
        not draft
        or not request.user.documents.filter(
            pk=draft["document_id"], kind="cv"
        ).exists()
    ):
        return missing_draft(request)
    return render(
        request,
        "candidates/cv_review.html",
        {**review_context(request, draft), "token": token},
    )


@candidate_required
@never_cache
@require_POST
def save_import(request, token):
    key = draft_key(request.user, token)
    draft = cache.get(key)
    if (
        not draft
        or not request.user.documents.filter(
            pk=draft["document_id"], kind="cv"
        ).exists()
    ):
        return missing_draft(request)
    if request.POST.get("action") == "cancel":
        cache.delete(key)
        messages.info(
            request, "CV suggestions discarded. Your saved profile is unchanged."
        )
        return redirect("candidates:profile")
    context = review_context(request, draft, request.POST)
    form, sections = context["form"], context["sections"]
    valid = form.is_valid()
    valid_sections = [section["formset"].is_valid() for section in sections]
    if valid and all(valid_sections):
        try:
            with transaction.atomic():
                # Serialize imports for this owner, including first profile creation.
                get_user_model().objects.select_for_update().get(pk=request.user.pk)
                profile = (
                    CandidateProfile.objects.select_for_update()
                    .filter(user=request.user)
                    .first()
                )
                if not cache.get(key):
                    return missing_draft(request)
                if profile_version(request.user) != draft["version"]:
                    form.add_error(
                        None,
                        "Your profile changed after this review started. Discard these suggestions and start again to include your latest changes.",
                    )
                else:
                    profile = profile or CandidateProfile(user=request.user)
                    additions = []
                    for section in sections:
                        prefix = section["prefix"]
                        identities = existing_identities(profile, prefix)
                        count = (
                            getattr(profile, RELATIONS[prefix]).count()
                            if profile.pk
                            else 0
                        )
                        for entry in section["formset"]:
                            if not entry.cleaned_data.get("include"):
                                continue
                            identity = entry_identity(prefix, entry.cleaned_data)
                            if identity in identities:
                                continue
                            identities.add(identity)
                            count += 1
                            additions.append(entry)
                        if count > section["maximum"]:
                            form.add_error(
                                None,
                                f"Your {section['title'].lower()} section would exceed its limit of {section['maximum']} entries. Uncheck some suggestions before saving.",
                            )
                    if not form.errors:
                        for name in form.cleaned_data["selected_fields"]:
                            setattr(profile, name, form.cleaned_data[name])
                        if form.cleaned_data["selected_fields"] or additions:
                            profile.full_clean()
                            profile.save()
                            for entry in additions:
                                item = entry.save(commit=False)
                                item.profile = profile
                                item.save()
                        cache.delete(key)
                        messages.success(
                            request,
                            "Your reviewed CV details have been saved to your profile.",
                        )
                        return redirect("candidates:profile")
        except ValidationError as error:
            form.add_error(None, error.messages)
        except IntegrityError:
            form.add_error(
                None,
                "Your profile changed while saving. Review your profile and start the import again.",
            )
    return render(
        request,
        "candidates/cv_review.html",
        {**context, "token": token, "has_errors": True},
    )
