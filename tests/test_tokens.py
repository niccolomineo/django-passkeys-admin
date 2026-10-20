"""Enrolment token tests."""

from datetime import UTC, datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils.crypto import get_random_string
from time_machine import travel

from passkeys_admin.conf import setting
from passkeys_admin.testing import PasskeyLoginMixin
from passkeys_admin.tokens import make_enrolment_token, passkey_state, read_enrolment_token

User = get_user_model()


class EnrolmentTokenTests(PasskeyLoginMixin, TestCase):
    """Tests for passkey enrolment tokens."""

    @classmethod
    def setUpTestData(cls) -> None:
        """Set up test data."""
        super().setUpTestData()
        cls.user = User.objects.create_user(
            username="staff", password=get_random_string(12), is_staff=True
        )

    def test_a_fresh_token_carries_the_user_and_state(self) -> None:
        """Test that a fresh token carries the user primary key and passkey state."""
        payload = read_enrolment_token(make_enrolment_token(self.user))
        self.assertEqual(payload, {"user": self.user.pk, "state": [], "login": ""})

    def test_the_state_follows_the_enrolled_passkeys(self) -> None:
        """Test that the passkey state follows the credentials the user owns."""
        credential = self.create_passkey(self.user)
        self.assertEqual(passkey_state(self.user), [credential.pk])

    def test_a_tampered_token_is_rejected(self) -> None:
        """Test that a tampered token is rejected."""
        self.assertIsNone(read_enrolment_token(f"{make_enrolment_token(self.user)}x"))

    def test_a_token_expires_after_the_maximum_age(self) -> None:
        """Test that a token expires once the maximum age has elapsed."""
        token = make_enrolment_token(self.user)
        expired = datetime.now(UTC) + timedelta(seconds=setting("ENROLMENT_MAX_AGE") + 60)
        with travel(expired, tick=False):
            self.assertIsNone(read_enrolment_token(token))
