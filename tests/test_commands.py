"""Management command tests."""

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils.crypto import get_random_string

from passkeys_admin.tokens import read_enrolment_token

User = get_user_model()


class EnrolPasskeyCommandTests(TestCase):
    """Tests for the enrol_passkey management command."""

    @classmethod
    def setUpTestData(cls) -> None:
        """Set up test data."""
        super().setUpTestData()
        cls.staff_user = User.objects.create_user(
            username="staff", password=get_random_string(12), is_staff=True
        )
        cls.regular_user = User.objects.create_user(
            username="regular", password=get_random_string(12)
        )

    def test_the_command_prints_a_usable_enrolment_link(self) -> None:
        """Test that the command prints a link carrying a valid enrolment token."""
        out = StringIO()
        call_command("enrol_passkey", "staff", "--base-url=http://localhost:8000", stdout=out)
        link = out.getvalue().strip().splitlines()[-1]
        self.assertTrue(link.startswith("http://localhost:8000/admin/passkeys/enrol/"))
        token = link.rstrip("/").rsplit("/", 1)[-1]
        self.assertEqual(
            read_enrolment_token(token), {"user": self.staff_user.pk, "state": [], "login": ""}
        )

    def test_the_command_honours_the_base_url_option(self) -> None:
        """Test that the command prefixes the link with the requested origin."""
        out = StringIO()
        call_command("enrol_passkey", "staff", "--base-url=https://example.com/", stdout=out)
        link = out.getvalue().strip().splitlines()[-1]
        self.assertTrue(link.startswith("https://example.com/admin/passkeys/enrol/"))

    def test_the_command_rejects_an_unknown_user(self) -> None:
        """Test that the command raises an error for an unknown user."""
        with self.assertRaisesMessage(CommandError, "with username nobody"):
            call_command("enrol_passkey", "nobody", "--base-url=http://x", stdout=StringIO())

    def test_the_command_rejects_a_non_staff_user(self) -> None:
        """Test that the command raises an error for a non-staff account."""
        with self.assertRaises(CommandError):
            call_command("enrol_passkey", "regular", "--base-url=http://x", stdout=StringIO())
