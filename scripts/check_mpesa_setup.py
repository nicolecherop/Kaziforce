"""Print sandbox readiness without exposing credentials or making payment requests."""

import os
from pathlib import Path
import sys

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django

django.setup()
from django.conf import settings
from mpesa.client import sandbox_ready

cfg = settings.MPESA_SANDBOX
print("M-Pesa endpoint: sandbox only")
print("Sandbox enabled:", cfg["enabled"])
print(
    "Consumer credentials configured:",
    bool(cfg["consumer_key"] and cfg["consumer_secret"]),
)
print("Shortcode/passkey configured:", bool(cfg["shortcode"] and cfg["passkey"]))
print("Ready for external sandbox testing:", sandbox_ready())
print("No payment or network request was made.")
