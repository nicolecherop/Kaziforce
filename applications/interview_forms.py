"""Recruiter interview details; times are entered in the site's Nairobi timezone."""

from django import forms
from django.utils import timezone
from .models import Interview


class InterviewForm(forms.ModelForm):
    starts_at = forms.DateTimeField(
        label="Interview date and time (East Africa Time, UTC+3)",
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}
        ),
        help_text="Choose a future date and time. The candidate will see the timezone alongside the invitation.",
    )

    class Meta:
        model = Interview
        fields = [
            "starts_at",
            "duration_minutes",
            "format",
            "location",
            "meeting_url",
            "instructions",
            "recruiter_name",
            "recruiter_email",
            "recruiter_phone",
        ]
        labels = {
            "duration_minutes": "Duration in minutes",
            "format": "Interview format",
            "meeting_url": "Video meeting link",
            "location": "Interview address",
            "instructions": "Message and preparation instructions",
            "recruiter_name": "Contact person",
            "recruiter_email": "Recruiter contact email",
            "recruiter_phone": "Recruiter phone number",
        }
        help_texts = {
            "meeting_url": "Required for a video call. Use an HTTPS or HTTP meeting link.",
            "location": "Include the venue, building, floor or room, and directions the candidate may need.",
            "recruiter_email": "Shared with the candidate so they can reply or ask questions.",
            "recruiter_phone": "Optional for video or in-person interviews; required for a phone interview.",
        }
        widgets = {
            "instructions": forms.Textarea(attrs={"rows": 4}),
            "recruiter_phone": forms.TextInput(attrs={"type": "tel"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["starts_at"].widget.attrs["min"] = timezone.localtime().strftime(
            "%Y-%m-%dT%H:%M"
        )
        self.fields["format"].choices = [
            (Interview.Format.IN_PERSON, "In person"),
            (Interview.Format.PHONE, "Phone call"),
            (Interview.Format.VIDEO, "Video call"),
        ]
        if self.instance._state.adding:
            self.initial.setdefault("format", Interview.Format.IN_PERSON)

    def clean(self):
        data = super().clean()
        if data.get("starts_at") and data["starts_at"] <= timezone.now():
            self.add_error("starts_at", "Choose a future date and time.")
        required = {
            "video": ("meeting_url", "Add a meeting link for the video call."),
            "in_person": ("location", "Add the interview address."),
            "phone": ("recruiter_phone", "Add a phone number the candidate can use."),
        }
        if data.get("format") in required:
            field, message = required[data["format"]]
            if not data.get(field):
                self.add_error(field, message)
        # Do not carry an old link or address into a different interview format.
        if data.get("format") != "video":
            data["meeting_url"] = ""
        if data.get("format") != "in_person":
            data["location"] = ""
        return data


class InterviewCancellationForm(forms.Form):
    reason = forms.CharField(
        label="Message to the candidate",
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Explain the cancellation or how you will arrange the next step.",
    )
