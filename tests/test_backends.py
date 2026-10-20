"""Authentication backend tests."""

from django.contrib.auth import authenticate, get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.utils.crypto import get_random_string

from passkeys_admin.backends import PasskeyOnlyStaffBackend
from passkeys_admin.constants import PASSKEY_SESSION_KEY

User = get_user_model()


class PasskeyOnlyStaffBackendTests(TestCase):
    """Tests refusing password authentication to accounts that need a passkey."""

    @classmethod
    def setUpTestData(cls) -> None:
        """Set up test data."""
        super().setUpTestData()
        cls.password = get_random_string(12)
        cls.customer = User.objects.create_user(username="customer", password=cls.password)
        cls.staff_user = User.objects.create_user(
            username="staff", password=cls.password, is_staff=True
        )

    def setUp(self) -> None:
        """Set up a request carrying a session."""
        self.request = RequestFactory().post("/")
        self.request.session = self.client.session

    def test_a_customer_may_authenticate_with_a_password(self) -> None:
        """Test that a customer still authenticates with a password."""
        user = authenticate(self.request, username="customer", password=self.password)
        self.assertEqual(user, self.customer)

    def test_a_staff_account_may_not_authenticate_with_a_password(self) -> None:
        """Test that a staff account is refused its own correct password."""
        user = authenticate(self.request, username="staff", password=self.password)
        self.assertIsNone(user)

    @override_settings(PASSKEYS_ADMIN_REQUIRED=False)
    def test_a_staff_account_may_use_a_password_where_passkeys_are_optional(self) -> None:
        """Test that a staff account signs in with a password where passkeys are optional."""
        user = authenticate(self.request, username="staff", password=self.password)
        self.assertEqual(user, self.staff_user)

    def test_a_wrong_password_is_refused(self) -> None:
        """Test that an incorrect password authenticates nobody."""
        user = authenticate(self.request, username="customer", password=get_random_string(12))
        self.assertIsNone(user)

    def test_an_inactive_customer_is_refused(self) -> None:
        """Test that a deactivated account cannot authenticate with its password."""
        self.customer.is_active = False
        self.customer.save(update_fields=["is_active"])
        user = authenticate(self.request, username="customer", password=self.password)
        self.assertIsNone(user)


class PasskeyOnlyStaffBackendPasskeyPathTests(TestCase):
    """Tests for the rules the backend applies to a passkey assertion."""

    backend = PasskeyOnlyStaffBackend()

    @classmethod
    def setUpTestData(cls) -> None:
        """Set up test data."""
        super().setUpTestData()
        cls.staff_user = User.objects.create_user(
            username="staff", password=get_random_string(12), is_staff=True
        )
        cls.customer = User.objects.create_user(username="customer", password=get_random_string(12))

    def test_a_staff_account_may_use_a_passkey(self) -> None:
        """Test that a staff account may authenticate with a passkey."""
        self.assertTrue(self.backend.may_authenticate(self.staff_user, False))

    def test_a_customer_may_not_use_a_passkey(self) -> None:
        """Test that a passkey belonging to a customer is refused."""
        self.assertFalse(self.backend.may_authenticate(self.customer, False))

    def test_an_inactive_staff_account_may_not_use_a_passkey(self) -> None:
        """Test that a deactivated staff account is refused its own passkey."""
        self.staff_user.is_active = False
        self.assertFalse(self.backend.may_authenticate(self.staff_user, False))

    def test_a_refusal_clears_the_passkey_session_mark(self) -> None:
        """Test that refusing an assertion leaves no passkey mark in the session."""
        request = RequestFactory().post("/")
        request.session = self.client.session
        request.session[PASSKEY_SESSION_KEY] = {"passkey": True, "id": 1}
        self.assertIsNone(authenticate(request))
        self.assertNotIn(PASSKEY_SESSION_KEY, request.session)

    def test_a_refusal_without_a_request_authenticates_nobody(self) -> None:
        """Test that a refusal with no request to clean up still refuses."""
        user = self.backend.authenticate(None, username="staff", password=self.staff_user.password)
        self.assertIsNone(user)
