"""Calendar constraints shared by upcoming-work forms; historical profiles are excluded."""

from datetime import date
from django.utils import timezone


def configure_future_dates(form, start="start_date", end="end_date"):
    today = timezone.localdate().isoformat()
    attrs = form.fields[start].widget.attrs
    attrs.update(
        {
            "min": today,
            "data-date-floor": today,
            "data-date-timezone": timezone.get_current_timezone_name(),
        }
    )
    if not end:
        return
    attrs["data-range-end"] = form[end].html_name
    value = form[start].value()
    try:
        selected = date.fromisoformat(str(value)).isoformat()
    except (ValueError, TypeError):
        selected = today
    form.fields[end].widget.attrs["min"] = max(today, selected)
