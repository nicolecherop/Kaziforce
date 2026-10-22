"""Explicit fields prevent clients from choosing owners, states or confirmations."""

from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.utils import timezone

from candidates.validators import validate_phone_number
from .contact_rules import (
    validate_no_contacts,
    BOOKING_CONTACT_MESSAGE,
    PUBLIC_CONTACT_MESSAGE,
)
from .models import (
    FreelancerProfile,
    FreelanceService,
    FreelanceProject,
    Booking,
    Message,
    Payment,
    Review,
)


def validate_contact_fields(form, data, names, message=PUBLIC_CONTACT_MESSAGE):
    """Attach a useful error to each affected field without changing saved text."""
    for name in names:
        if data.get(name):
            try:
                validate_no_contacts(data[name], message)
            except ValidationError as error:
                form.add_error(name, error)


class FreelancerForm(forms.ModelForm):
    class Meta:
        model = FreelancerProfile
        fields = [
            "title",
            "about",
            "location",
            "work_mode",
            "rate",
            "rate_unit",
            "available_from",
            "share_professional_profile",
            "accepting_bookings",
        ]
        labels = {
            "title": "What do you offer?",
            "about": "About your freelance work",
            "rate": "Starting rate (KES)",
            "accepting_bookings": "Accepting new bookings",
            "share_professional_profile": "Show my professional skills, experience, education, certificates and portfolio links to signed-in recruiters",
        }
        widgets = {
            "about": forms.Textarea(attrs={"rows": 5}),
            "available_from": forms.DateInput(attrs={"type": "date"}),
        }
        help_texts = {
            "rate": "A starting rate; agree the full price for each booking before accepting.",
            "share_professional_profile": "Your CV and uploaded documents stay private. Contact details and portfolio links unlock for a recruiter only after you accept a booking with them.",
            "accepting_bookings": "Turn off to hide your listing and stop new enquiries. Existing bookings and messages remain available.",
            "available_from": "Accepted bookings reserve their full date range.",
        }

    def clean(self):
        data = super().clean()
        validate_contact_fields(self, data, ("title", "about", "location"))
        if data.get("accepting_bookings") and not data.get(
            "share_professional_profile"
        ):
            self.add_error(
                "share_professional_profile",
                "Allow recruiters to view your professional information before enabling bookings.",
            )
        return data


class ServiceForm(forms.ModelForm):
    class Meta:
        model = FreelanceService
        fields = ["title", "description"]
        labels = {
            "title": "Service title",
            "description": "What does this service include?",
        }
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}

    def clean(self):
        data = super().clean()
        validate_contact_fields(self, data, ("title", "description"))
        return data


class OwnedServiceFormSet(BaseInlineFormSet):
    def add_fields(self, form, index):
        super().add_fields(form, index)
        form.fields["DELETE"].label = "Remove this service"

    def clean(self):
        super().clean()
        for form in self.forms:
            service = form.cleaned_data.get("id")
            if service and service.profile_id != self.instance.pk:
                raise ValidationError(
                    "A service belongs to a different freelance profile. Reload this page and try again."
                )


ServiceFormSet = inlineformset_factory(
    FreelancerProfile,
    FreelanceService,
    form=ServiceForm,
    formset=OwnedServiceFormSet,
    extra=1,
    max_num=10,
    validate_max=True,
    absolute_max=20,
    can_delete=True,
)


class ProjectForm(forms.ModelForm):
    skill_names = forms.CharField(
        max_length=1700,
        required=False,
        label="Relevant skills",
        help_text="Separate skills with commas. Up to 20 skills.",
    )

    class Meta:
        model = FreelanceProject
        fields = [
            "title",
            "description",
            "skill_names",
            "location",
            "work_mode",
            "budget",
            "start_date",
            "end_date",
            "status",
        ]
        labels = {
            "description": "Scope and deliverables",
            "budget": "Total budget (KES)",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }
        help_texts = {
            "description": "Describe what needs to be delivered and how you will agree completion.",
            "budget": "An indicative budget. Confirm the final price in a booking.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_start = self.instance.start_date
        if self.instance.pk and not self.instance._state.adding:
            self.fields["skill_names"].initial = ", ".join(self.instance.skills)

    def clean_skill_names(self):
        validate_no_contacts(self.cleaned_data["skill_names"])
        names = list(
            dict.fromkeys(
                " ".join(s.split())
                for s in self.cleaned_data["skill_names"].split(",")
                if s.strip()
            )
        )
        if len(names) > 20 or any(len(s) > 80 for s in names):
            raise ValidationError(
                "Use up to 20 skills, each no longer than 80 characters."
            )
        return names

    def clean(self):
        data = super().clean()
        validate_dates(
            self,
            data,
            allow_past=not self.instance._state.adding
            and data.get("start_date") == self.original_start,
        )
        # Editing a published project never changes an existing booking agreement.
        self.instance.skills = data.get("skill_names", [])
        validate_contact_fields(self, data, ("title", "description", "location"))
        return data


def validate_dates(form, data, allow_past=False):
    start, end = data.get("start_date"), data.get("end_date")
    if start and end and end < start:
        form.add_error("end_date", "The end date must be on or after the start date.")
    if start and start < timezone.localdate() and not allow_past:
        form.add_error("start_date", "Choose today or a future date.")


class BookingForm(forms.ModelForm):
    share_contacts = forms.BooleanField(
        label="Share these recruiter contact details with this freelancer once they accept the booking"
    )

    class Meta:
        model = Booking
        fields = [
            "title",
            "scope",
            "location",
            "start_date",
            "end_date",
            "total_price",
            "cancellation_terms",
            "recruiter_name",
            "recruiter_email",
            "recruiter_phone",
        ]
        labels = {
            "scope": "Scope and deliverables",
            "total_price": "Total agreed price (KES)",
            "location": "Meeting or work location / Remote",
            "cancellation_terms": "Cancellation and refund agreement",
        }
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "scope": forms.Textarea(attrs={"rows": 5}),
            "cancellation_terms": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {
            "total_price": "No advance payment is required. Record payment after the work is completed.",
            "cancellation_terms": "Agree when cancellation is allowed and how to settle any completed work or refunds.",
        }

    def clean(self):
        data = super().clean()
        validate_dates(self, data)
        validate_contact_fields(
            self,
            data,
            ("title", "scope", "location", "cancellation_terms", "recruiter_name"),
            BOOKING_CONTACT_MESSAGE,
        )
        return data


class AcceptBookingForm(forms.Form):
    freelancer_name = forms.CharField(max_length=160, label="Your name")
    freelancer_email = forms.EmailField(label="Your contact email")
    freelancer_phone = forms.CharField(
        max_length=32,
        required=False,
        label="Your phone number",
        validators=[validate_phone_number],
    )
    agree = forms.BooleanField(
        label="I accept the scope, dates, full price and cancellation terms, and agree to share these contact details with this recruiter"
    )


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ["body"]
        labels = {"body": "Your message"}
        widgets = {"body": forms.Textarea(attrs={"rows": 3, "maxlength": 3000})}


class CancellationForm(forms.Form):
    reason = forms.CharField(
        max_length=1500,
        label="Reason for cancellation",
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["kind", "method", "amount", "reference"]
        labels = {
            "amount": "Amount (KES)",
            "reference": "Reference or receipt note (optional)",
        }
        help_texts = {
            "reference": "Do not include a PIN, bank password or card details."
        }

    def __init__(self, *args, is_recruiter, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["kind"].choices = [
            c
            for c in Payment.Kind.choices
            if c[0] == (Payment.Kind.BALANCE if is_recruiter else Payment.Kind.REFUND)
        ]


class ReviewForm(forms.ModelForm):
    def clean_comment(self):
        comment = self.cleaned_data["comment"]
        validate_no_contacts(comment)
        return comment

    class Meta:
        model = Review
        fields = ["rating", "comment"]
        widgets = {
            "rating": forms.Select(choices=[(n, f"{n} / 5") for n in range(5, 0, -1)]),
            "comment": forms.Textarea(attrs={"rows": 4}),
        }


class ReportForm(forms.Form):
    reason = forms.CharField(
        max_length=1500,
        label="Describe the concern",
        widget=forms.Textarea(attrs={"rows": 3}),
    )
