import unittest

from app.core.privacy import redact_payload


class TestPrivacyRedaction(unittest.TestCase):
    def test_redacts_sensitive_keys(self) -> None:
        payload = {
            "email": "user@example.com",
            "nested": {
                "api_key": "secret-key",
                "safe": "value",
            },
            "rows": [{"phone": "+79990000000", "city": "Kaliningrad"}],
        }
        redacted = redact_payload(payload)
        self.assertEqual(redacted["email"], "[REDACTED]")
        self.assertEqual(redacted["nested"]["api_key"], "[REDACTED]")
        self.assertEqual(redacted["nested"]["safe"], "value")
        self.assertEqual(redacted["rows"][0]["phone"], "[REDACTED]")

    def test_truncates_long_string(self) -> None:
        payload = {"note": "x" * 800}
        redacted = redact_payload(payload, max_text_len=120)
        self.assertTrue(redacted["note"].endswith("[TRUNCATED]"))


if __name__ == "__main__":
    unittest.main()
