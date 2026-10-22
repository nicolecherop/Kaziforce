"""The tunnel origin cannot forward admin, sign-in, document or arbitrary routes."""

from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
from threading import Thread
from unittest.mock import patch
from django.test import SimpleTestCase
from scripts.serve_mpesa_callback import CallbackHandler, CALLBACK_PATH


class CallbackGatewayTests(SimpleTestCase):
    def setUp(self):
        CallbackHandler.requests.clear()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), CallbackHandler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.forward = patch(
            "scripts.serve_mpesa_callback.forward_callback", return_value=True
        ).start()
        self.addCleanup(patch.stopall)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(
        self, path, method="POST", payload=None, content_type="application/json"
    ):
        conn = HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            conn.request(
                method,
                path,
                body=json.dumps(
                    payload
                    or {
                        "Body": {
                            "stkCallback": {
                                "CheckoutRequestID": "test-checkout",
                                "MerchantRequestID": "test-merchant",
                            }
                        }
                    }
                ),
                headers={"Content-Type": content_type},
            )
            result = conn.getresponse()
            return result.status, result.read()
        finally:
            conn.close()

    def test_other_paths_and_get_requests_never_reach_django(self):
        for path in (
            "/",
            "/admin/",
            "/accounts/sign-in/",
            "/private_uploads/file.pdf",
            CALLBACK_PATH + "?next=/admin/",
            "/payments/mpesa/%63allback/",
        ):
            self.assertEqual(self.request(path)[0], 404)
        self.assertEqual(self.request(CALLBACK_PATH, method="GET")[0], 404)
        self.forward.assert_not_called()

    def test_only_expected_ids_are_forwarded(self):
        refs = {
            "CheckoutRequestID": "test-checkout",
            "MerchantRequestID": "test-merchant",
        }
        status, body = self.request(
            CALLBACK_PATH,
            payload={
                "Body": {
                    "stkCallback": {
                        **refs,
                        "ResultCode": 0,
                        "CallbackMetadata": {"PhoneNumber": "private-number"},
                    }
                }
            },
        )
        self.assertEqual(status, 200)
        self.forward.assert_called_once_with({"Body": {"stkCallback": refs}})
        self.assertNotIn(b"private-number", body)

    def test_invalid_callbacks_and_content_types_are_rejected(self):
        self.assertEqual(self.request(CALLBACK_PATH, payload={"invalid": True})[0], 400)
        self.assertEqual(self.request(CALLBACK_PATH, content_type="text/plain")[0], 415)
        self.forward.assert_not_called()

    def test_upstream_error_is_generic_and_cannot_expose_debug_output(self):
        self.forward.return_value = False
        status, body = self.request(CALLBACK_PATH)
        self.assertEqual(status, 502)
        self.assertEqual(json.loads(body), {"error": "Callback service unavailable"})

    def test_large_callbacks_are_rejected_without_forwarding(self):
        # Reject the announced length before reading a body. Sending the large
        # body while the server closes early can cause a Windows TCP reset.
        conn = HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            conn.putrequest("POST", CALLBACK_PATH)
            conn.putheader("Content-Type", "application/json")
            conn.putheader("Content-Length", "17000")
            conn.endheaders()
            self.assertEqual(conn.getresponse().status, 413)
        finally:
            conn.close()
        self.forward.assert_not_called()
