"""Callback-only local origin for temporary M-Pesa sandbox HTTPS tunnels.

Never point the public tunnel directly at Django's development server.
"""

import argparse
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
from threading import Lock, BoundedSemaphore
import time
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import URLError

CALLBACK_PATH = "/payments/mpesa/callback/"
UPSTREAM = "http://127.0.0.1:8001" + CALLBACK_PATH


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def forward_callback(payload):
    request = Request(
        UPSTREAM,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with build_opener(NoRedirects()).open(request, timeout=5) as response:
            return response.status == 200
    except (URLError, OSError):
        return False


class CallbackHandler(BaseHTTPRequestHandler):
    server_version = "KaziForceCallback"
    sys_version = ""
    slots = BoundedSemaphore(10)
    requests = deque()
    rate_lock = Lock()

    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, format, *args):
        pass  # Do not log provider bodies, headers, phone numbers or request paths.

    def reply(self, status, result):
        body = json.dumps(result).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.reply(404, {"error": "Not found"})

    def do_HEAD(self):
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        if self.path != CALLBACK_PATH:
            return self.reply(404, {"error": "Not found"})
        with self.rate_lock:
            now = time.monotonic()
            while self.requests and self.requests[0] < now - 60:
                self.requests.popleft()
            if len(self.requests) >= 60:
                return self.reply(429, {"error": "Too many requests"})
            self.requests.append(now)
        if not self.slots.acquire(blocking=False):
            return self.reply(429, {"error": "Busy"})
        try:
            return self.receive_callback()
        finally:
            self.slots.release()

    def receive_callback(self):
        if (
            self.headers.get("Transfer-Encoding")
            or len(self.headers.get_all("Content-Length", [])) != 1
        ):
            return self.reply(400, {"error": "A single content length is required"})
        try:
            length = int(self.headers["Content-Length"])
        except (TypeError, ValueError):
            return self.reply(400, {"error": "Invalid content length"})
        if not 0 < length <= 16384:
            return self.reply(413, {"error": "Invalid payload size"})
        if (
            self.headers.get("Content-Type", "").split(";")[0].lower()
            != "application/json"
        ):
            return self.reply(415, {"error": "JSON required"})
        try:
            body = json.loads(self.rfile.read(length))["Body"]["stkCallback"]
            refs = {
                key: body[key] for key in ("CheckoutRequestID", "MerchantRequestID")
            }
            if not all(
                isinstance(value, str)
                and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value)
                for value in refs.values()
            ):
                raise ValueError
        except (ValueError, TypeError, KeyError, OSError):
            return self.reply(400, {"error": "Invalid callback"})
        # Drop receipt claims and personal information; Django only needs the IDs
        # to record a hint. Authenticated Daraja queries confirm actual status.
        if not forward_callback({"Body": {"stkCallback": refs}}):
            return self.reply(502, {"error": "Callback service unavailable"})
        return self.reply(200, {"ResultCode": 0, "ResultDesc": "Accepted"})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8014)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), CallbackHandler)
    print(f"Callback-only gateway listening on 127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
