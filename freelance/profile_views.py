"""Optional listing management and private-to-recruiters professional previews."""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from candidates.access import candidate_required
from jobs.access import recruiter_required
from .access import workspace_required
from .forms import FreelancerForm, ServiceFormSet, MessageForm
from .search_forms import FreelancerSearchForm
from .models import FreelancerProfile
from .selectors import (
    visible_profiles,
    visible_projects,
    freelance_search,
    profile_reviews,
)
from .services import start_conversation
from .contact_rules import contact_sharing_allowed


@workspace_required
def home(request):
    return redirect(
        "freelance:profile" if request.user.role == "candidate" else "freelance:find"
    )


@candidate_required
@require_http_methods(["GET", "POST"])
def profile_edit(request):
    with transaction.atomic():
        # Serializes simultaneous first-time profile creation without duplicate accounts.
        if request.method == "POST":
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
        profile = FreelancerProfile.objects.filter(
            user=request.user
        ).first() or FreelancerProfile(
            user=request.user, available_from=timezone.localdate()
        )
        data = request.POST if request.method == "POST" else None
        form = FreelancerForm(data, instance=profile)
        services = ServiceFormSet(data, instance=profile, prefix="services")
        if request.method == "POST" and form.is_valid() and services.is_valid():
            profile = form.save()
            services.instance = profile
            services.save()
            messages.success(request, "Your freelance profile has been saved.")
            return redirect("freelance:profile")
    return render(
        request, "freelance/profile_form.html", {"form": form, "services": services}
    )


@candidate_required
def my_profile(request):
    profile = FreelancerProfile.objects.filter(user=request.user).first()
    return render(
        request,
        "freelance/my_profile.html",
        {
            "profile": profile,
            "reviews": profile_reviews(profile)[:10] if profile else [],
        },
    )


@recruiter_required
def find(request):
    form = FreelancerSearchForm(request.GET)
    project = None
    valid = form.is_valid()
    if valid and form.cleaned_data.get("project"):
        project = get_object_or_404(
            request.user.freelance_projects.all(), pk=form.cleaned_data["project"]
        )
    profiles = freelance_search(form.cleaned_data, project) if valid else []
    page = Paginator(profiles, 12).get_page(request.GET.get("page"))
    return render(
        request,
        "freelance/find.html",
        {
            "form": form,
            "page": page,
            "project": project,
            "projects": request.user.freelance_projects.filter(status="open"),
        },
    )


@recruiter_required
@require_http_methods(["GET", "POST"])
def profile_detail(request, pk):
    profile = get_object_or_404(visible_profiles(), pk=pk)
    professional = getattr(profile.user, "candidate_profile", None)
    form = MessageForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            conversation = start_conversation(
                request.user, profile.pk, form.cleaned_data["body"]
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            return redirect("freelance:conversation", pk=conversation.pk)
    return render(
        request,
        "freelance/profile_detail.html",
        {
            "profile": profile,
            "professional": professional,
            "reviews": profile_reviews(profile)[:20],
            "form": form,
            "contacts_unlocked": contact_sharing_allowed(request.user.pk, profile.pk),
        },
    )
