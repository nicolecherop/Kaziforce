"""Validation shared by optional candidate and recruiter contact fields."""

import re
from django.core.exceptions import ValidationError


def validate_phone_number(value):
    if not re.fullmatch(r"\+?[0-9][0-9 ()-]{5,30}", value) or not (
        7 <= len(re.sub(r"[^0-9]", "", value)) <= 15
    ):
        raise ValidationError(
            "Enter a valid phone number, including the country code where possible."
        )
