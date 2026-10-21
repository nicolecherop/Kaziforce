"""Small presentation helpers shared by the workspace templates."""

from copy import copy

from django import template

from pages.presentation import contact_email, public_text

register = template.Library()
register.filter("site_text", public_text)
register.filter("contact_email", contact_email)


@register.filter
def site_field(field):
    """Display clean initial labels without changing submitted data or form state."""
    if field.form.is_bound:
        return field
    initial = public_text(field.initial)
    if initial == field.initial:
        return field
    presented = copy(field)
    presented.initial = initial
    return presented


@register.filter
def initials(value):
    words = str(value or "K").split()
    return "".join(
        word[0] for word in (words[:1] + words[-1:] if len(words) > 1 else words)
    ).upper()


@register.filter
def priority_label(value):
    return {1: "Standard", 2: "Important", 3: "High"}.get(value, "Standard")
