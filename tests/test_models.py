"""Signal receiver tests."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils.crypto import get_random_string

from passkeys_admin.constants import ENROLMENT_SESSION_KEY
from passkeys_admin.testing import PasskeyLoginMixin
from passkeys_admin.tokens import make_enrolment_token

User = get_user_model()


class EndEnrolmentGrantTests(PasskeyLoginMixin, TestCase):
    """Tests that a real login ends the grant an enrolment link handed out."""

    @classmethod
    def setUpTestData(cls) -> None:
        """Set up test data."""
        super().setUpTestData()
        cls.staff_user = User.objects.create_user(
            username="staff", password=get_random_string(12), is_staff=True
        )

    def test_a_later_login_ends_the_grant_and_its_expiry(self) -> None:
        """Test that a subsequent login clears the grant and restores the expiry."""
        self.client.get(
            reverse("staff:passkey_enrol", args=(make_enrolment_token(self.staff_user),))
        )
        self.passkey_login(self.staff_user)
        self.assertNotIn(ENROLMENT_SESSION_KEY, self.client.session)
        self.assertEqual(self.client.session.get_expiry_age(), settings.SESSION_COOKIE_AGE)

    def test_an_ordinary_login_is_left_alone(self) -> None:
        """Test that a login without a grant leaves the session expiry untouched."""
        self.passkey_login(self.staff_user)
        self.assertEqual(self.client.session.get_expiry_age(), settings.SESSION_COOKIE_AGE)
