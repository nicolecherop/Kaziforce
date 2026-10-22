"""Display protection for older freelance text without changing saved evidence."""

from django import template
from freelance.contact_rules import redact_contacts

register = template.Library()


@register.filter
def contact_safe(value, unlocked=False):
    # Leave autoescaping enabled. Never mark user-supplied text as safe HTML.
    return value if unlocked else redact_contacts(value)
