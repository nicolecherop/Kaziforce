"""Conservative contact detection for freelance text, with no external services.

This is a practical guard for obvious details, not a guarantee against deliberate
disguises. Currency amounts, ordinary dates and common technology names are preserved.
Saved text is never silently rewritten; older content is masked only when displayed.
"""

import re
import unicodedata

from django.core.exceptions import ValidationError

PUBLIC_CONTACT_MESSAGE = (
    "Keep contact details and web links out of public freelance information. "
    "Share them in your private conversation after a booking is accepted."
)
PRIVATE_CONTACT_MESSAGE = (
    "Contact details and web links can be shared after a booking is accepted. "
    "For now, use these messages to agree the work, dates and price."
)
BOOKING_CONTACT_MESSAGE = (
    "Use the dedicated contact fields for phone numbers and emails. "
    "Contact details and web links become available after the booking is accepted."
)
HIDDEN_CONTACT = "[Contact details hidden until booking]"

EMAIL = re.compile(
    r"(?<![\w.+-])[\w.%+-]+\s*(?:@|\[at\]|\(at\))\s*"
    r"[\w.-]+\s*(?:\.|\[dot\]|\(dot\))\s*[a-z]{2,63}\b",
    re.I,
)
LINK = re.compile(
    r"\b(?:https?://|www\.|mailto:|tel:|sms:|skype:|tg:|whatsapp:)[^\s<>]+", re.I
)
DOMAIN = re.compile(
    r"\b(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+"
    r"(?:com|org|net|ke|io|me|dev|app|co|uk|info|biz|africa|site|online|xyz|ai|test|edu)"
    r"\b(?:[/?:#][^\s<>]*)?",
    re.I,
)
SOCIAL_HANDLE = re.compile(
    r"\b(?:instagram|telegram|linkedin|facebook|twitter|tiktok|discord|skype|signal)"
    r"\s*(?:(?:handle|username|id)\s*)?[:=\-]?\s*@[\w.]{2,}",
    re.I,
)
PHONE = re.compile(r"(?<![\w+])\+?\d(?:[ \t().-]*\d){6,14}(?![\w])")
PHONE_CUE = re.compile(
    r"(?:phone|mobile|call|text|whatsapp|tel|contact)\s*(?:number|me)?\s*[:=\-]?\s*$",
    re.I,
)
DATE = re.compile(r"\b(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4})\b")
NUMBER_RANGE = re.compile(r"^\d{1,9}\s*-\s*\d{1,9}$")
CURRENCY_CUE = re.compile(
    r"(?:KES|KSH\.?|USD|GBP|EUR|budget|price|cost|fee)\s*[:=]?\s*$", re.I
)
TECHNOLOGY_NAMES = {"asp.net", "ado.net", "vb.net"}


def normalized_text(value):
    text = unicodedata.normalize("NFKC", str(value or ""))
    return "".join(char for char in text if unicodedata.category(char) != "Cf")


def contact_spans(text):
    spans = [
        m.span()
        for pattern in (EMAIL, LINK, SOCIAL_HANDLE)
        for m in pattern.finditer(text)
    ]
    for match in DOMAIN.finditer(text):
        if match.group().casefold() not in TECHNOLOGY_NAMES:
            spans.append(match.span())
    # Exclude complete dates before scanning so adjacent dates cannot form a phone,
    # and a date beside a real phone cannot swallow that phone's opening digits.
    phone_text = list(text)
    for match in DATE.finditer(text):
        phone_text[match.start() : match.end()] = "D" * (match.end() - match.start())
    for match in PHONE.finditer("".join(phone_text)):
        value = text[match.start() : match.end()]
        digits = "".join(c for c in value if c.isdigit())
        preceding = text[max(0, match.start() - 35) : match.start()]
        if not value.startswith(("+", "0")):
            if NUMBER_RANGE.fullmatch(value) or CURRENCY_CUE.search(preceding):
                continue
        separated = len(re.findall(r"[ ().-]+", value)) >= 2
        if (
            value.startswith("+")
            or (value.startswith("0") and len(digits) >= 9)
            or len(digits) >= 10
            or (separated and len(digits) >= 9)
            or PHONE_CUE.search(preceding)
        ):
            spans.append(match.span())
    # Merge overlapping email/domain/link matches so a partial address cannot remain.
    merged = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def validate_no_contacts(value, message=PUBLIC_CONTACT_MESSAGE):
    if contact_spans(normalized_text(value)):
        raise ValidationError(message, code="contact_before_booking")


def redact_contacts(value):
    if not isinstance(value, str):
        return value
    text = normalized_text(value)
    spans = contact_spans(text)
    if not spans:
        return value
    for start, end in reversed(spans):
        text = text[:start] + HIDDEN_CONTACT + text[end:]
    return text


def contact_sharing_allowed(recruiter_id, freelancer_id):
    """A past acceptance belongs to this pair, never to all of a recruiter's workers.

    Declined, withdrawn or merely requested bookings do not qualify. After contact
    sharing has been agreed, cancellation cannot undisclose those earlier details.
    """
    from .models import Booking

    return Booking.objects.filter(
        conversation__recruiter_id=recruiter_id,
        conversation__freelancer_id=freelancer_id,
        accepted_at__isnull=False,
    ).exists()
