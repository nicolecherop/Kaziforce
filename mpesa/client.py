"""Minimal Daraja client: sandbox host only, bounded timeouts, no credential logging."""

import base64
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

SANDBOX_HOST = "https://sandbox.safaricom.co.ke"


class ProviderError(Exception):
    """A sanitized error; provider bodies may contain confidential information."""


class ProviderRejected(ProviderError):
    """The provider explicitly rejected submission, so no checkout was accepted."""


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def sandbox_ready():
    cfg = settings.MPESA_SANDBOX
    if not cfg["enabled"] or not all(
        cfg[k]
        for k in (
            "consumer_key",
            "consumer_secret",
            "passkey",
            "shortcode",
            "callback_url",
        )
    ):
        return False
    url = urlsplit(cfg["callback_url"])
    return bool(
        re.fullmatch(r"\d{5,6}", cfg["shortcode"])
        and url.scheme == "https"
        and url.hostname
        and url.hostname not in {"localhost", "127.0.0.1", "::1"}
        and not url.username
        and not url.password
        and not url.query
        and not url.fragment
        and url.path == "/payments/mpesa/callback/"
    )


def normalize_phone(value):
    value = re.sub(r"[\s()+-]", "", value)
    if value.startswith("0"):
        value = "254" + value[1:]
    elif len(value) == 9:
        value = "254" + value
    if not re.fullmatch(r"254[17]\d{8}", value):
        raise ValidationError(
            "Enter a Kenyan mobile number, for example 0712345678 or 254712345678."
        )
    return value


class DarajaSandboxClient:
    def __init__(self):
        if not sandbox_ready():
            raise ProviderError("M-Pesa sandbox setup is incomplete.")
        self.config = settings.MPESA_SANDBOX

    def _request(self, path, authorization, payload=None):
        body = json.dumps(payload).encode() if payload is not None else None
        request = Request(
            SANDBOX_HOST + path,
            data=body,
            headers={
                "Authorization": authorization,
                "Content-Type": "application/json",
            },
        )
        try:
            with build_opener(NoRedirects()).open(request, timeout=15) as response:
                raw = response.read(65537)
            if len(raw) > 65536:
                raise ProviderError("Unexpected response from the sandbox.")
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ProviderError("Unexpected response from the sandbox.")
            return result
        except (HTTPError, URLError, OSError, ValueError) as error:
            raise ProviderError(
                "The sandbox request could not be confirmed. Check its status before retrying."
            ) from None

    def _token(self):
        credentials = (
            f'{self.config["consumer_key"]}:{self.config["consumer_secret"]}'.encode()
        )
        response = self._request(
            "/oauth/v1/generate?grant_type=client_credentials",
            "Basic " + base64.b64encode(credentials).decode(),
        )
        token = response.get("access_token")
        if not isinstance(token, str) or not token or len(token) > 4096:
            raise ProviderError("Sandbox authentication was unsuccessful.")
        return token

    def _password(self, shortcode):
        stamp = timezone.localtime().strftime("%Y%m%d%H%M%S")
        password = base64.b64encode(
            f'{shortcode}{self.config["passkey"]}{stamp}'.encode()
        ).decode()
        return stamp, password

    def initiate(self, transaction):
        stamp, password = self._password(transaction.shortcode)
        try:
            token = self._token()
        except ProviderError:
            raise ProviderRejected(
                "Sandbox authentication failed before submission."
            ) from None
        response = self._request(
            "/mpesa/stkpush/v1/processrequest",
            "Bearer " + token,
            {
                "BusinessShortCode": transaction.shortcode,
                "Password": password,
                "Timestamp": stamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": transaction.amount,
                "PartyA": transaction.phone_number,
                "PartyB": transaction.shortcode,
                "PhoneNumber": transaction.phone_number,
                "CallBackURL": self.config["callback_url"],
                "AccountReference": "KF" + transaction.booking_id.hex[:10],
                "TransactionDesc": "FreelanceWork",
            },
        )
        if "ResponseCode" in response and str(response["ResponseCode"]) != "0":
            raise ProviderRejected(
                "Sandbox request rejected. Check your configuration and test details."
            )
        if str(response.get("ResponseCode")) != "0" or not all(
            isinstance(response.get(k), str) and 0 < len(response[k]) <= 128
            for k in ("CheckoutRequestID", "MerchantRequestID")
        ):
            raise ProviderError("The sandbox submission result was incomplete.")
        return response

    def query(self, transaction):
        stamp, password = self._password(transaction.shortcode)
        return self._request(
            "/mpesa/stkpushquery/v1/query",
            "Bearer " + self._token(),
            {
                "BusinessShortCode": transaction.shortcode,
                "Password": password,
                "Timestamp": stamp,
                "CheckoutRequestID": transaction.checkout_request_id,
            },
        )
