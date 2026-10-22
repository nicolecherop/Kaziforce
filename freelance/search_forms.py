from django import forms
from .models import FreelancerProfile


class FreelancerSearchForm(forms.Form):
    project = forms.UUIDField(required=False, widget=forms.HiddenInput)
    q = forms.CharField(max_length=120, required=False, label="Service or skill")
    location = forms.CharField(max_length=120, required=False)
    work_mode = forms.ChoiceField(
        required=False,
        choices=[("", "Any work arrangement"), *FreelancerProfile.WorkMode.choices],
    )
    rate_unit = forms.ChoiceField(
        required=False,
        choices=[("", "Any pricing basis"), *FreelancerProfile.RateUnit.choices],
    )
    maximum_rate = forms.DecimalField(
        required=False,
        min_value=1,
        max_digits=12,
        decimal_places=2,
        label="Maximum starting rate (KES)",
    )
    start_date = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    end_date = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"})
    )

    def clean(self):
        data = super().clean()
        if data.get("maximum_rate") and not data.get("rate_unit"):
            self.add_error(
                "rate_unit", "Choose a pricing basis to compare starting rates."
            )
        start, end = data.get("start_date"), data.get("end_date")
        if bool(start) != bool(end):
            raise forms.ValidationError("Enter both dates to check availability.")
        if start and end and end < start:
            self.add_error("end_date", "Choose an end date on or after the start date.")
        return data
