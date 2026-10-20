"""Form tests."""

from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.forms import PasswordResetForm
from django.http import HttpRequest
from django.test import RequestFactory, TestCase, override_settings
from django.utils.crypto import get_random_string

from passkeys_admin.forms import PasskeyAuthenticationForm, PasskeyOnlyPasswordResetMixin

User = get_user_model()


class ResetForm(PasskeyOnlyPasswordResetMixin, PasswordResetForm):
    """Bare password reset form carrying the passkey restriction."""


class AcceptingBackend(BaseBackend):
    """Backend standing in for a completed ceremony, which needs a real device."""

    def authenticate(self, request: HttpRequest | None, **credentials: Any) -> AbstractBaseUser:
        """Return the account the ceremony would have resolved."""
        return User.objects.first()


class PasskeyAuthenticationFormTests(TestCase):
    """Tests for the passkey-only login form."""

    def test_it_requires_an_assertion(self) -> None:
        """Test that the form is invalid without a passkey assertion."""
        form = PasskeyAuthenticationForm(RequestFactory().post("/"), data={})
        self.assertFalse(form.is_valid())
        self.assertIn("passkeys", form.errors)

    def test_it_rejects_an_unrecognised_assertion(self) -> None:
        """Test that an assertion the backend refuses is reported as invalid."""
        request = RequestFactory().post("/", {"passkeys": "{}"})
        request.session = self.client.session
        form = PasskeyAuthenticationForm(request, data={"passkeys": "{}"})
        self.assertFalse(form.is_valid())
        self.assertIn("That passkey was not accepted. Please try again.", form.errors["__all__"])

    def test_it_exposes_no_password_field(self) -> None:
        """Test that the form offers nothing but the assertion."""
        self.assertEqual(list(PasskeyAuthenticationForm().fields), ["passkeys"])


@override_settings(AUTHENTICATION_BACKENDS=["tests.test_forms.AcceptingBackend"])
class PasskeyAuthenticationFormSuccessTests(TestCase):
    """Tests for what the form does once a backend has accepted an assertion."""

    @classmethod
    def setUpTestData(cls) -> None:
        """Set up test data."""
        super().setUpTestData()
        cls.staff_user = User.objects.create_user(
            username="staff", password=get_random_string(12), is_staff=True
        )

    def test_it_keeps_the_authenticated_user(self) -> None:
        """Test that the form hands the authenticated user to the login view."""
        request = RequestFactory().post("/", {"passkeys": "{}"})
        request.session = self.client.session
        form = PasskeyAuthenticationForm(request, data={"passkeys": "{}"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.get_user(), self.staff_user)


class PasskeyOnlyPasswordResetMixinTests(TestCase):
    """Tests withholding password resets from accounts that must use a passkey."""

    @classmethod
    def setUpTestData(cls) -> None:
        """Set up test data."""
        super().setUpTestData()
        cls.customer = User.objects.create_user(
            username="customer", email="customer@example.com", password=get_random_string(12)
        )
        cls.staff_user = User.objects.create_user(
            username="staff",
            email="staff@example.com",
            password=get_random_string(12),
            is_staff=True,
        )

    def test_a_customer_receives_a_reset(self) -> None:
        """Test that a customer is offered a password reset."""
        self.assertEqual(list(ResetForm().get_users(self.customer.email)), [self.customer])

    def test_a_staff_account_receives_no_reset(self) -> None:
        """Test that a staff account is excluded from password resets."""
        self.assertEqual(list(ResetForm().get_users(self.staff_user.email)), [])

    @override_settings(PASSKEYS_ADMIN_REQUIRED=False)
    def test_a_staff_account_receives_a_reset_where_passkeys_are_optional(self) -> None:
        """Test that a staff account is offered a reset where passkeys are optional."""
        self.assertEqual(list(ResetForm().get_users(self.staff_user.email)), [self.staff_user])
