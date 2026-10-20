"""Account endpoints and role-specific entry pages."""

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from candidates.selectors import profile_for, section_status

from .forms import EmailAuthenticationForm, RegistrationForm
from .models import User


class SignInView(LoginView):
    template_name = "accounts/sign_in.html"
    authentication_form = EmailAuthenticationForm


@require_http_methods(["GET", "POST"])
def create_account(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")
    selected_role = request.GET.get("role", User.Role.CANDIDATE)
    if selected_role not in {User.Role.CANDIDATE, User.Role.RECRUITER}:
        selected_role = User.Role.CANDIDATE
    form = RegistrationForm(
        request.POST if request.method == "POST" else None,
        initial={"role": selected_role},
    )
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                user = form.save()
        except IntegrityError:
            # A concurrent registration may win after form validation.
            if User.objects.filter(email__iexact=form.cleaned_data["email"]).exists():
                form.add_error(
                    "email",
                    "An account with this email already exists. Please sign in.",
                )
            else:
                raise
        else:
            login(request, user)
            return redirect("accounts:dashboard")
    return render(request, "accounts/create_account.html", {"form": form})


@login_required
def dashboard(request):
    if request.user.role == User.Role.RECRUITER:
        template = "recruiters/dashboard.html"
    elif request.user.role == User.Role.CANDIDATE:
        profile = profile_for(request.user)
        return render(
            request,
            "candidates/dashboard.html",
            {
                "profile": profile,
                "profile_sections": section_status(profile),
            },
        )
    else:
        template = "accounts/administrator_home.html"
    return render(request, template)
