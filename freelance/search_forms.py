from django import forms
from config.date_fields import configure_future_dates
from .forms import validate_dates
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
        label="Pricing basis",
        required=False,
        choices=[("", "Any pricing basis"), *FreelancerProfile.RateUnit.choices],
    )
    minimum_rate = forms.DecimalField(
        required=False,
        min_value=1,
        max_digits=12,
        decimal_places=2,
        label="Minimum price (KES)",
        widget=forms.NumberInput(attrs={"placeholder": "No minimum", "step": "0.01"}),
    )
    maximum_rate = forms.DecimalField(
        required=False,
        min_value=1,
        max_digits=12,
        decimal_places=2,
        label="Maximum price (KES)",
        help_text="Filters the worker's starting rate for the selected pricing basis. Agree the full booking price directly.",
        widget=forms.NumberInput(attrs={"placeholder": "No maximum", "step": "0.01"}),
    )
    start_date = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    end_date = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        configure_future_dates(self)

    def clean(self):
        data = super().clean()
        minimum, maximum = data.get("minimum_rate"), data.get("maximum_rate")
        if (minimum is not None or maximum is not None) and not data.get("rate_unit"):
            self.add_error(
                "rate_unit", "Choose a pricing basis to compare starting rates."
            )
        if minimum is not None and maximum is not None and maximum < minimum:
            self.add_error(
                "maximum_rate", "The maximum price must be at least the minimum price."
            )
        start, end = data.get("start_date"), data.get("end_date")
        if bool(start) != bool(end):
            raise forms.ValidationError("Enter both dates to check availability.")
        validate_dates(self, data)
        return data
