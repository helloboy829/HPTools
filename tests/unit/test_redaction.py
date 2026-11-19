import unittest

from aiperf.security.redaction import redact_fields


class RedactionTests(unittest.TestCase):
    def test_redacts_sensitive_keys_recursively_and_normalizes_names(self) -> None:
        payload = {
            "Authorization": "Bearer auth-value",
            "request": {
                "x-api-key": "api-key-value",
                "clientSecret": "secret-value",
                "password_hash": "password-value",
                "Cookie": "cookie-value",
                "signature": "signature-value",
            },
        }

        redacted = redact_fields(payload)

        self.assertEqual(redacted["Authorization"], "[REDACTED]")
        self.assertEqual(redacted["request"]["x-api-key"], "[REDACTED]")
        self.assertEqual(redacted["request"]["clientSecret"], "[REDACTED]")
        self.assertEqual(redacted["request"]["password_hash"], "[REDACTED]")
        self.assertEqual(redacted["request"]["Cookie"], "[REDACTED]")
        self.assertEqual(redacted["request"]["signature"], "[REDACTED]")

    def test_preserves_benign_values_and_sequence_types(self) -> None:
        payload = {"status": "ok", "latency_ms": 12.5, "items": ["a", {"token": "secret"}]}

        redacted = redact_fields(payload)

        self.assertEqual(redacted, {"status": "ok", "latency_ms": 12.5, "items": ["a", {"token": "[REDACTED]"}]})
        self.assertIsInstance(redacted["items"], list)

    def test_does_not_mutate_input(self) -> None:
        payload = {"token": "keep original in caller object"}

        redact_fields(payload)

        self.assertEqual(payload["token"], "keep original in caller object")

    def test_does_not_inspect_free_form_string_content(self) -> None:
        text = "free-form text with token=abc"

        self.assertEqual(redact_fields(text), text)


if __name__ == "__main__":
    unittest.main()
