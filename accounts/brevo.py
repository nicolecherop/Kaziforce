"""Deliver Django transactional email through Brevo's HTTPS API."""

import json
from email.utils import parseaddr
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


def address(value):
    name, email = parseaddr(value)
    return {"email": email, **({"name": name} if name else {})}


class EmailBackend(BaseEmailBackend):
    def __init__(self, *args, timeout=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.timeout = timeout or settings.EMAIL_TIMEOUT

    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages or ():
            if not message.recipients():
                continue
            payload = {
                "sender": address(message.from_email),
                "subject": message.subject,
                "textContent": message.body,
            }
            for key in ("to", "cc", "bcc"):
                recipients = getattr(message, key)
                if recipients:
                    payload[key] = [address(value) for value in recipients]
            if message.reply_to:
                payload["replyTo"] = address(message.reply_to[0])
            for alternative in getattr(message, "alternatives", ()):
                if alternative.mimetype == "text/html":
                    payload["htmlContent"] = alternative.content
            request = Request(
                "https://api.brevo.com/v3/smtp/email",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json", "api-key": settings.BREVO_API_KEY},
            )
            try:
                with urlopen(request, timeout=self.timeout):
                    sent += 1
            except OSError:
                if not self.fail_silently:
                    raise
        return sent
