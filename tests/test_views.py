"""Authentication ceremony view tests."""

from http import HTTPStatus

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse_lazy

from passkeys_admin.conf import setting


class AuthenticationCeremonyTests(TestCase):
    """Tests for the pre-login authentication ceremony endpoint."""

    url = reverse_lazy("staff:passkey_authenticate")

    def setUp(self) -> None:
        """Start each test with an empty rate-limit counter."""
        cache.clear()

    def test_an_anonymous_visitor_is_issued_options(self) -> None:
        """Test that an anonymous visitor is issued usernameless options."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["publicKey"]["allowCredentials"], [])

    @override_settings(PASSKEYS_ADMIN_CEREMONY_RATE=2)
    def test_a_client_starting_too_many_ceremonies_is_refused(self) -> None:
        """Test that a client exceeding the rate is refused further ceremonies."""
        for _ in range(setting("CEREMONY_RATE")):
            self.assertEqual(self.client.get(self.url).status_code, HTTPStatus.OK)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, HTTPStatus.TOO_MANY_REQUESTS)
        self.assertEqual(response.json()["status"], "ERR")

    @override_settings(PASSKEYS_ADMIN_CEREMONY_RATE=1)
    def test_each_client_address_is_counted_on_its_own(self) -> None:
        """Test that one address exhausting its rate leaves another unaffected."""
        self.client.get(self.url, REMOTE_ADDR="192.0.2.1")
        refused = self.client.get(self.url, REMOTE_ADDR="192.0.2.1")
        other = self.client.get(self.url, REMOTE_ADDR="192.0.2.2")
        self.assertEqual(refused.status_code, HTTPStatus.TOO_MANY_REQUESTS)
        self.assertEqual(other.status_code, HTTPStatus.OK)
