import unittest

from app.core.config import Settings


class TestSecurityConfig(unittest.TestCase):
    def test_cookie_secure_defaults_to_false_in_development(self) -> None:
        settings = Settings()
        settings.app_env = "development"
        settings.auth_cookie_secure = None
        self.assertFalse(settings.cookie_secure)

    def test_cookie_secure_defaults_to_true_in_production(self) -> None:
        settings = Settings()
        settings.app_env = "production"
        settings.auth_cookie_secure = None
        self.assertTrue(settings.cookie_secure)

    def test_production_requires_non_default_secret(self) -> None:
        settings = Settings()
        settings.app_env = "production"
        settings.auth_cookie_secure = False
        with self.assertRaises(RuntimeError):
            settings.validate_production_safety()


if __name__ == "__main__":
    unittest.main()
