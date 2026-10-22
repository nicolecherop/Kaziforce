from django import forms
from allauth.socialaccount.forms import SignupForm


class GoogleSignupForm(SignupForm):
    role = forms.ChoiceField(
        choices=[("candidate", "Candidate"), ("recruiter", "Recruiter")],
        label="Account type",
    )
    accept_terms = forms.BooleanField(label="I agree to the Terms and Privacy Policy.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The email comes from the verified provider response, never a submitted edit.
        self.fields["email"].disabled = True
