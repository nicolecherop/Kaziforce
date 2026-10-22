from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_http_methods
from candidates.access import candidate_required
from jobs.access import recruiter_required
from .access import workspace_required
from .forms import ProjectForm, MessageForm
from .models import FreelanceProject, FreelancerProfile
from .selectors import visible_projects, skill_keys
from .services import start_conversation


@workspace_required
def projects(request):
    own = request.user.role == "recruiter"
    qs = request.user.freelance_projects.all() if own else visible_projects()
    q = request.GET.get("q", "")[:120].strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(description__icontains=q)
            | Q(location__icontains=q)
        )
    results = list(qs)
    if not own:
        professional = getattr(request.user, "candidate_profile", None)
        keys = (
            skill_keys([s.name for s in professional.skills.all()])
            if professional
            else set()
        )
        for project in results:
            project.relevant_skills = len(keys & skill_keys(project.skills))
        results.sort(key=lambda p: (-p.relevant_skills, -p.created_at.timestamp()))
    return render(
        request,
        "freelance/projects.html",
        {
            "own": own,
            "page": Paginator(results, 12).get_page(request.GET.get("page")),
            "q": q,
        },
    )


@recruiter_required
@require_http_methods(["GET", "POST"])
def project_edit(request, pk=None):
    instance = (
        get_object_or_404(request.user.freelance_projects.all(), pk=pk)
        if pk
        else FreelanceProject(recruiter=request.user)
    )
    form = ProjectForm(
        request.POST if request.method == "POST" else None, instance=instance
    )
    if request.method == "POST" and form.is_valid():
        project = form.save()
        messages.success(
            request,
            "Your project has been saved. Existing booking agreements are unchanged.",
        )
        return redirect("freelance:project_detail", pk=project.pk)
    return render(
        request, "freelance/project_form.html", {"form": form, "project": instance}
    )


@workspace_required
@require_http_methods(["GET", "POST"])
def project_detail(request, pk):
    if request.user.role == "recruiter":
        project = get_object_or_404(request.user.freelance_projects.all(), pk=pk)
    else:
        project = get_object_or_404(visible_projects(), pk=pk)
    profile = FreelancerProfile.objects.filter(
        user=request.user, accepting_bookings=True, share_professional_profile=True
    ).first()
    form = MessageForm(request.POST if request.method == "POST" else None)
    if request.method == "POST":
        if request.user.role != "candidate" or not profile:
            messages.error(
                request,
                "Enable your freelance profile before sending a project proposal.",
            )
        elif form.is_valid():
            try:
                conversation = start_conversation(
                    request.user, profile.pk, form.cleaned_data["body"], project.pk
                )
            except ValidationError as error:
                form.add_error(None, error)
            else:
                return redirect("freelance:conversation", pk=conversation.pk)
    return render(
        request,
        "freelance/project_detail.html",
        {"project": project, "profile": profile, "form": form},
    )
