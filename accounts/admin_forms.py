"""Email sign-in for active staff, using the existing account authentication."""

from django import forms
from .forms import EmailAuthenticationForm


class AdminEmailAuthenticationForm(EmailAuthenticationForm):
    required_css_class = "required"

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise forms.ValidationError(
                self.error_messages["invalid_login"], code="invalid_login"
            )
