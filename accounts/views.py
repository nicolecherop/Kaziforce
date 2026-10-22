"""Account endpoints and role-specific entry pages."""

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from pages.workspace import candidate_dashboard, recruiter_dashboard

from .forms import EmailAuthenticationForm, RegistrationForm
from .models import User


class SignInView(LoginView):
    template_name = "accounts/sign_in.html"
    authentication_form = EmailAuthenticationForm

    def post(self, request, *args, **kwargs):
        from allauth.core import ratelimit

        key = request.POST.get("username", "").strip().lower()
        blocked = ratelimit.consume_or_429(request, action="login", key=key)
        if blocked:
            return blocked
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        from allauth.account.internal.flows.login import perform_password_login
        from allauth.account.models import Login

        user = form.get_user()
        destination = self.get_success_url()
        # A partially completed challenge never retains an earlier authenticated session.
        logout(self.request)
        return perform_password_login(
            self.request,
            {"email": user.email},
            Login(user=user, email=user.email, redirect_url=destination),
        )


@require_http_methods(["GET", "POST"])
def create_account(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")
    if request.method == "POST":
        from allauth.core import ratelimit

        blocked = ratelimit.consume_or_429(
            request,
            action="login",
            key="signup:" + request.POST.get("email", "").strip().lower(),
        )
        if blocked:
            return blocked
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
                from allauth.account.models import EmailAddress

                user = form.save()
                EmailAddress.objects.create(
                    user=user, email=user.email, primary=True, verified=False
                )
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
            from allauth.account.internal.flows.login import perform_password_login
            from allauth.account.models import Login
            from django.urls import reverse

            logout(request)
            return perform_password_login(
                request,
                {"email": user.email},
                Login(
                    user=user,
                    email=user.email,
                    redirect_url=reverse("accounts:dashboard"),
                ),
            )
    return render(request, "accounts/create_account.html", {"form": form})


@login_required
def dashboard(request):
    if request.user.is_active and request.user.is_staff:
        return redirect("admin:index")
    if request.user.role == User.Role.RECRUITER:
        return render(
            request, "recruiters/dashboard.html", recruiter_dashboard(request.user)
        )
    elif request.user.role == User.Role.CANDIDATE:
        return render(
            request,
            "candidates/dashboard.html",
            candidate_dashboard(request.user),
        )
    else:
        raise PermissionDenied("Staff access is required to open administration.")
