from django import forms
from .client import normalize_phone


class SandboxPaymentForm(forms.Form):
    phone_number = forms.CharField(
        label="M-Pesa phone number",
        max_length=32,
        widget=forms.TextInput(attrs={"type": "tel", "autocomplete": "tel"}),
        help_text="Enter the number that should receive the payment prompt. Never enter an M-Pesa PIN on this website.",
    )
    amount = forms.DecimalField(
        label="Amount (KES)",
        min_value=1,
        max_value=100000,
        max_digits=6,
        decimal_places=0,
        help_text="Whole shillings only; no more than the outstanding booking balance.",
    )
    request_key = forms.UUIDField(widget=forms.HiddenInput)

    def clean_phone_number(self):
        return normalize_phone(self.cleaned_data["phone_number"])
