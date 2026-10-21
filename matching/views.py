from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .skills import skill_suggestions


@login_required
@require_GET
def search_skills(request):
    response = JsonResponse(
        {"suggestions": skill_suggestions(request.GET.get("q", ""))}
    )
    response["Cache-Control"] = "private, no-store"
    return response
