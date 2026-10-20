"""Validated account forms. Public registration cannot grant staff privileges."""

from uuid import uuid4

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User


class RegistrationForm(UserCreationForm):
    full_name = forms.CharField(max_length=150, label="Full name")
    email = forms.EmailField(label="Email address")
    role = forms.ChoiceField(
        choices=[
            (User.Role.CANDIDATE, "Candidate"),
            (User.Role.RECRUITER, "Recruiter"),
        ],
        initial=User.Role.CANDIDATE,
        widget=forms.RadioSelect,
    )
    accept_terms = forms.BooleanField(
        label="I agree to the prototype Terms and Privacy Policy.",
        error_messages={
            "required": "Please read and accept the prototype terms to continue."
        },
    )

    class Meta:
        model = User
        fields = ("full_name", "email", "role", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        hints = {
            "full_name": ("Enter your full name", "name"),
            "email": ("you@company.com", "email"),
            "password1": ("Create a password", "new-password"),
            "password2": ("Confirm your password", "new-password"),
        }
        for name, (placeholder, autocomplete) in hints.items():
            self.fields[name].widget.attrs.update(
                {"placeholder": placeholder, "autocomplete": autocomplete}
            )
        self.fields["password1"].help_text = (
            "Use at least 8 characters and avoid common or entirely numeric passwords."
        )
        self.fields["password2"].label = "Confirm password"
        self.fields["password2"].help_text = ""

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "An account with this email already exists. Please sign in."
            )
        return email

    def clean_full_name(self):
        value = " ".join(self.cleaned_data["full_name"].split())
        if not value:
            raise forms.ValidationError("Enter your full name.")
        return value

    def _post_clean(self):
        # Populate identity before Django checks password similarity.
        name = self.cleaned_data.get("full_name", "").split(" ", 1)
        self.instance.first_name = name[0]
        self.instance.last_name = name[1] if len(name) > 1 else ""
        self.instance.username = uuid4().hex
        super()._post_clean()


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(
            attrs={
                "autocomplete": "email",
                "placeholder": "you@company.com",
                "autofocus": True,
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "current-password",
                "placeholder": "Enter your password",
            }
        ),
    )
    error_messages = {"invalid_login": "The email address or password is incorrect."}

    def clean(self):
        email = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        if email and password:
            user = User.objects.filter(email__iexact=email.strip()).first()
            # An impossible username invokes Django's dummy hash for unknown emails.
            username = user.username if user else "!unknown-email"
            self.user_cache = authenticate(
                self.request, username=username, password=password
            )
            if self.user_cache is None:
                raise forms.ValidationError(
                    self.error_messages["invalid_login"], code="invalid_login"
                )
            self.confirm_login_allowed(self.user_cache)
        return self.cleaned_data
