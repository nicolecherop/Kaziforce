"""Email-verification enrollment and explicit Google connection management."""

import time
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from allauth.account.internal.flows.login import perform_password_login
from allauth.account.models import Login
from allauth.account.views import ConfirmLoginCodeView
from allauth.core import ratelimit
from allauth.socialaccount.models import SocialAccount
from .auth_support import (
    SECURITY_ACTION,
    email_codes_ready,
    signup_verification_pending,
)


class CurrentPasswordForm(forms.Form):
    password = forms.CharField(
        label="Current password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        value = self.cleaned_data["password"]
        if not self.user.check_password(value):
            raise forms.ValidationError("The password is incorrect.")
        return value


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def security(request):
    user = request.user
    form = CurrentPasswordForm(
        request.POST if request.method == "POST" else None, user=user
    )
    if request.method == "POST":
        blocked = ratelimit.consume_or_429(
            request, action="login", key=f"security:{user.pk}"
        )
        if blocked:
            return blocked
        if not user.has_usable_password():
            form.add_error(
                None, "Manage your sign-in protection through your Google account."
            )
        elif form.is_valid():
            action = request.POST.get("action")
            if action in {"enable", "disable"}:
                if (
                    action == "disable"
                    and user.is_staff
                    and settings.EMAIL_TWO_STEP_ENABLED
                ):
                    form.add_error(
                        None, "Email verification is required for administrator access."
                    )
                elif not email_codes_ready():
                    form.add_error(
                        None,
                        "Email verification is currently unavailable. Please try again later.",
                    )
                else:
                    logout(request)
                    request.session[SECURITY_ACTION] = {
                        "user": user.pk,
                        "action": action,
                    }
                    return perform_password_login(
                        request,
                        {"email": user.email},
                        Login(
                            user=user,
                            email=user.email,
                            redirect_url=reverse("accounts:security"),
                        ),
                    )
            elif action == "connect_google":
                if not settings.GOOGLE_SIGNIN_ENABLED:
                    form.add_error(None, "Google sign-in is currently unavailable.")
                else:
                    request.session["google_connection"] = {
                        "user": user.pk,
                        "at": time.time(),
                    }
                    return redirect(reverse("google_login") + "?process=connect")
            elif action == "disconnect_google":
                SocialAccount.objects.filter(user=user, provider="google").delete()
                request.session.pop("google_connection", None)
                messages.success(
                    request,
                    "Google has been disconnected. Your email and password still work.",
                )
                return redirect("accounts:security")
            else:
                form.add_error(None, "Choose an available security action.")
    return render(
        request,
        "accounts/security.html",
        {
            "form": form,
            "google_connected": SocialAccount.objects.filter(
                user=user, provider="google"
            ).exists(),
            "staff_verification_required": user.is_staff
            and settings.EMAIL_TWO_STEP_ENABLED,
        },
    )


class EmailCodeView(ConfirmLoginCodeView):
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if "code" in form.fields:
            form.fields["code"].widget.attrs.update(
                autocomplete="one-time-code", inputmode="numeric"
            )
        return form

    def post(self, request, *args, **kwargs):
        blocked = ratelimit.consume_or_429(
            request, action="confirm_login_code", key=str(self.stage.login.user.pk)
        )
        if blocked:
            return blocked
        return super().post(request, *args, **kwargs)

    def _resend_form_valid(self, form):
        state = self._process.state
        last_sent = state.get("last_sent_at", state["at"])
        if time.time() - last_sent < 60:
            messages.error(
                self.request, "Please wait one minute before requesting another code."
            )
            return redirect("account_confirm_login_code")
        response = super()._resend_form_valid(form)
        state["last_sent_at"] = time.time()
        self._process.persist()
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["confirming_new_account"] = signup_verification_pending(
            self.stage.login.user
        )
        email = context.get("email", "")
        local, _, domain = email.partition("@")
        context["masked_email"] = (
            (local[:1] + "***@" + domain) if domain else "your email address"
        )
        return context
