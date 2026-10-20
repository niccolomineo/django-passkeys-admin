"""Admin site tests."""

from http import HTTPStatus

from django.contrib.auth import BACKEND_SESSION_KEY, get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.test import TestCase, override_settings
from django.urls import reverse, reverse_lazy
from django.utils.crypto import get_random_string
from unbrowsed import parse_html

from passkeys_admin.conf import setting
from passkeys_admin.constants import BACKEND
from passkeys_admin.testing import PasskeyLoginMixin
from passkeys_admin.tokens import make_enrolment_token

User = get_user_model()


def enrolment_url(user: AbstractBaseUser) -> str:
    """Return an enrolment link carrying a fresh token for the given user."""
    return reverse("staff:passkey_enrol", args=(make_enrolment_token(user),))


class AdminLoginTests(PasskeyLoginMixin, TestCase):
    """Tests for the passkey-only admin login view."""

    url = reverse_lazy("staff:login")

    @classmethod
    def setUpTestData(cls) -> None:
        """Set up test data."""
        super().setUpTestData()
        cls.password = get_random_string(12)
        cls.staff_user = User.objects.create_user(
            username="staff", password=cls.password, is_staff=True
        )

    def test_get_renders_the_passkey_login_template(self) -> None:
        """Test that a GET renders the passkey login template."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "passkeys_admin/login.html")

    def test_get_offers_a_passkey_button_wired_to_the_ceremony(self) -> None:
        """Test that the login page offers a button starting the authentication ceremony."""
        response = self.client.get(self.url)
        dom = parse_html(response.content.decode())
        button = dom.css_first("#passkey-verification-button")
        self.assertEqual(button.attributes["data-begin-url"], reverse("staff:passkey_authenticate"))
        self.assertIsNotNone(dom.css_first('#passkey-login-form input[name="passkeys"]'))

    @override_settings(PASSKEYS_ADMIN_REQUIRED=False)
    def test_get_falls_back_to_the_plain_login_where_passkeys_are_optional(self) -> None:
        """Test that the admin login is the ordinary one where passkeys are optional."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "admin/login.html")
        dom = parse_html(response.content.decode())
        self.assertIsNotNone(dom.css_first('input[name="password"]'))

    @override_settings(PASSKEYS_ADMIN_REQUIRED=False)
    def test_a_password_session_reaches_the_admin_where_passkeys_are_optional(self) -> None:
        """Test that a staff session with no passkey reaches the admin where they are optional."""
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("staff:index"))
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_get_omits_any_credentials_field(self) -> None:
        """Test that the login page exposes no username or password field."""
        response = self.client.get(self.url)
        dom = parse_html(response.content.decode())
        self.assertIsNone(dom.css_first('input[type="password"]'))
        self.assertIsNone(dom.css_first('input[name="username"]'))
        self.assertIsNone(dom.css_first('input[name="password"]'))

    def test_get_carries_the_next_target(self) -> None:
        """Test that the login page carries the next target in a hidden field."""
        target = reverse("staff:passkeys")
        response = self.client.get(f"{self.url}?next={target}")
        dom = parse_html(response.content.decode())
        self.assertEqual(dom.css_first('input[name="next"]').attributes["value"], target)

    def test_get_defaults_the_next_target_to_the_index(self) -> None:
        """Test that the login page defaults the next target to the admin index."""
        response = self.client.get(self.url)
        dom = parse_html(response.content.decode())
        self.assertEqual(
            dom.css_first('input[name="next"]').attributes["value"], reverse("staff:index")
        )

    def test_post_with_credentials_is_refused(self) -> None:
        """Test that posting credentials to the login page authenticates nobody."""
        response = self.client.post(self.url, {"username": "staff", "password": self.password})
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_get_redirects_a_passkey_verified_user(self) -> None:
        """Test that a passkey verified user is redirected away from the login page."""
        self.passkey_login(self.staff_user)
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("staff:index"), fetch_redirect_response=False)


class AdminPermissionTests(PasskeyLoginMixin, TestCase):
    """Tests for admin access requiring a passkey verified session."""

    url = reverse_lazy("staff:index")

    @classmethod
    def setUpTestData(cls) -> None:
        """Set up test data."""
        super().setUpTestData()
        cls.staff_user = User.objects.create_user(
            username="staff", password=get_random_string(12), is_staff=True, is_superuser=True
        )

    def test_passkey_verified_staff_reaches_the_index(self) -> None:
        """Test that passkey verified staff reach the admin index."""
        self.passkey_login(self.staff_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_password_session_is_refused(self) -> None:
        """Test that a staff session without a passkey is refused by the admin."""
        self.client.force_login(self.staff_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, HTTPStatus.FOUND)

    def test_a_session_whose_passkey_was_deleted_is_refused(self) -> None:
        """Test that deleting the passkey behind a session shuts that session out."""
        self.passkey_login(self.staff_user).delete()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, HTTPStatus.FOUND)

    def test_anonymous_visitor_is_refused(self) -> None:
        """Test that an anonymous visitor is refused by the admin."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, HTTPStatus.FOUND)


class PasskeysViewTests(PasskeyLoginMixin, TestCase):
    """Tests for the passkey management page."""

    url = reverse_lazy("staff:passkeys")

    @classmethod
    def setUpTestData(cls) -> None:
        """Set up test data."""
        super().setUpTestData()
        cls.staff_user = User.objects.create_user(
            username="staff", password=get_random_string(12), is_staff=True
        )
        cls.other_user = User.objects.create_user(
            username="other", password=get_random_string(12), is_staff=True
        )
        cls.regular_user = User.objects.create_user(
            username="regular", password=get_random_string(12)
        )

    def test_anonymous_visitor_is_redirected_to_login(self) -> None:
        """Test that an anonymous visitor is redirected to the admin login."""
        response = self.client.get(self.url)
        self.assertRedirects(
            response, f"/admin/login/?next={self.url}", fetch_redirect_response=False
        )

    def test_non_staff_is_redirected_to_login(self) -> None:
        """Test that a non-staff user is redirected to the admin login."""
        self.client.force_login(self.regular_user)
        response = self.client.get(self.url)
        self.assertRedirects(
            response, f"/admin/login/?next={self.url}", fetch_redirect_response=False
        )

    def test_a_plain_staff_session_is_redirected_to_login(self) -> None:
        """Test that a staff session with neither passkey nor enrolment is refused."""
        self.client.force_login(self.staff_user)
        response = self.client.get(self.url)
        self.assertRedirects(
            response, f"/admin/login/?next={self.url}", fetch_redirect_response=False
        )

    def test_an_enrolment_session_reaches_the_page(self) -> None:
        """Test that a session created by an enrolment link reaches the page."""
        self.client.get(enrolment_url(self.staff_user))
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "passkeys_admin/passkeys.html")

    def test_an_enrolment_session_is_offered_no_delete_button(self) -> None:
        """Test that an enrolment session is shown no delete button."""
        self.create_passkey(self.staff_user, name="Mine")
        self.create_passkey(self.staff_user, name="Spare")
        self.client.get(enrolment_url(self.staff_user))
        response = self.client.get(self.url)
        dom = parse_html(response.content.decode())
        self.assertIsNone(dom.css_first('form[action*="/passkeys/delete/"]'))

    def test_a_verified_admin_is_offered_a_delete_button(self) -> None:
        """Test that a passkey verified admin is shown a delete button."""
        credential = self.passkey_login(self.staff_user)
        response = self.client.get(self.url)
        dom = parse_html(response.content.decode())
        action = reverse("staff:passkey_delete", args=(credential.pk,))
        self.assertIsNotNone(dom.css_first(f'form[action="{action}"]'))

    def test_page_offers_a_field_to_name_the_device(self) -> None:
        """Test that the page lets the operator name the device being enrolled."""
        self.passkey_login(self.staff_user)
        response = self.client.get(self.url)
        dom = parse_html(response.content.decode())
        self.assertIsNotNone(dom.css_first("#passkey-name"))

    def test_page_offers_a_registration_button_wired_to_the_ceremony(self) -> None:
        """Test that the page offers a button starting the registration ceremony."""
        self.passkey_login(self.staff_user)
        response = self.client.get(self.url)
        dom = parse_html(response.content.decode())
        button = dom.css_first("#passkey-register-button")
        self.assertEqual(button.attributes["data-begin-url"], reverse("staff:passkey_register"))
        self.assertEqual(
            button.attributes["data-complete-url"], reverse("staff:passkey_register_complete")
        )

    def test_page_lists_only_the_current_user_passkeys(self) -> None:
        """Test that the page lists only the passkeys of the current user."""
        self.passkey_login(self.staff_user, name="Mine")
        self.create_passkey(self.other_user, name="Theirs")
        response = self.client.get(self.url)
        self.assertContains(response, "Mine")
        self.assertNotContains(response, "Theirs")


class PasskeyDeleteViewTests(PasskeyLoginMixin, TestCase):
    """Tests for deleting a passkey."""

    @classmethod
    def setUpTestData(cls) -> None:
        """Set up test data."""
        super().setUpTestData()
        cls.staff_user = User.objects.create_user(
            username="staff", password=get_random_string(12), is_staff=True
        )
        cls.other_user = User.objects.create_user(
            username="other", password=get_random_string(12), is_staff=True
        )

    def test_get_returns_method_not_allowed(self) -> None:
        """Test that a GET request returns HTTP 405."""
        credential = self.passkey_login(self.staff_user)
        response = self.client.get(reverse("staff:passkey_delete", args=(credential.pk,)))
        self.assertEqual(response.status_code, HTTPStatus.METHOD_NOT_ALLOWED)

    def test_deleting_one_of_several_passkeys_succeeds(self) -> None:
        """Test that deleting one of several passkeys removes it."""
        credential = self.passkey_login(self.staff_user, name="First")
        spare = self.create_passkey(self.staff_user, name="Second")
        response = self.client.post(reverse("staff:passkey_delete", args=(spare.pk,)), follow=True)
        self.assertQuerySetEqual(
            self.staff_user.userpasskey_set.values_list("pk", flat=True), [credential.pk]
        )
        self.assertEqual(
            [message.message for message in response.context["messages"]],
            ["The passkey has been deleted."],
        )

    def test_deleting_the_last_passkey_is_refused(self) -> None:
        """Test that deleting the last remaining passkey is refused."""
        credential = self.passkey_login(self.staff_user)
        response = self.client.post(
            reverse("staff:passkey_delete", args=(credential.pk,)), follow=True
        )
        self.assertQuerySetEqual(
            self.staff_user.userpasskey_set.values_list("pk", flat=True), [credential.pk]
        )
        self.assertEqual(
            [message.message for message in response.context["messages"]],
            ["Your last remaining passkey cannot be deleted."],
        )

    def test_deleting_another_user_passkey_is_refused(self) -> None:
        """Test that a passkey owned by another user survives a delete attempt."""
        self.passkey_login(self.staff_user, name="First")
        self.create_passkey(self.staff_user, name="Second")
        theirs = self.create_passkey(self.other_user, name="Theirs")
        response = self.client.post(reverse("staff:passkey_delete", args=(theirs.pk,)), follow=True)
        self.assertTrue(self.other_user.userpasskey_set.filter(pk=theirs.pk).exists())
        self.assertEqual(
            [message.message for message in response.context["messages"]],
            ["That passkey could not be found."],
        )


class PasskeyEnrolViewTests(PasskeyLoginMixin, TestCase):
    """Tests for the bootstrap passkey enrolment link."""

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

    def test_a_valid_token_signs_the_staff_user_in(self) -> None:
        """Test that a valid token signs the staff user in and shows the page."""
        response = self.client.get(enrolment_url(self.staff_user), follow=True)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "passkeys_admin/passkeys.html")
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.staff_user.pk)

    @override_settings(
        AUTHENTICATION_BACKENDS=["django.contrib.auth.backends.ModelBackend", BACKEND]
    )
    def test_the_session_it_grants_names_the_passkey_backend_wherever_it_is_listed(
        self,
    ) -> None:
        """Test that the granted session names the passkey backend even when listed second."""
        response = self.client.get(enrolment_url(self.staff_user), follow=True)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(self.client.session[BACKEND_SESSION_KEY], BACKEND)

    def test_the_session_it_grants_expires_with_the_token(self) -> None:
        """Test that the granted session expires when the token would have."""
        self.client.get(enrolment_url(self.staff_user))
        self.assertEqual(self.client.session.get_expiry_age(), setting("ENROLMENT_MAX_AGE"))

    def test_the_session_it_grants_cannot_reach_the_admin(self) -> None:
        """Test that the session an enrolment link grants cannot reach the admin."""
        self.client.get(enrolment_url(self.staff_user))
        response = self.client.get(reverse("staff:index"))
        self.assertEqual(response.status_code, HTTPStatus.FOUND)

    def test_the_session_it_grants_cannot_delete_a_passkey(self) -> None:
        """Test that the session an enrolment link grants cannot delete a passkey."""
        first = self.create_passkey(self.staff_user, name="First")
        self.create_passkey(self.staff_user, name="Second")
        self.client.get(enrolment_url(self.staff_user))
        url = reverse("staff:passkey_delete", args=(first.pk,))
        response = self.client.post(url)
        self.assertRedirects(response, f"/admin/login/?next={url}", fetch_redirect_response=False)
        self.assertTrue(self.staff_user.userpasskey_set.filter(pk=first.pk).exists())

    def test_a_tampered_token_returns_not_found(self) -> None:
        """Test that a tampered token returns HTTP 404."""
        url = f"{enrolment_url(self.staff_user).rstrip('/')}tampered/"
        self.assertEqual(self.client.get(url).status_code, HTTPStatus.NOT_FOUND)

    def test_a_token_for_a_non_staff_user_returns_not_found(self) -> None:
        """Test that a token issued for a non-staff user returns HTTP 404."""
        response = self.client.get(enrolment_url(self.regular_user))
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_a_token_is_void_once_a_passkey_is_enrolled(self) -> None:
        """Test that a token stops working once the user enrols a passkey."""
        url = enrolment_url(self.staff_user)
        self.create_passkey(self.staff_user)
        self.assertEqual(self.client.get(url).status_code, HTTPStatus.NOT_FOUND)

    def test_a_token_is_void_once_it_has_been_followed(self) -> None:
        """Test that a token stops working after it has been redeemed once."""
        url = enrolment_url(self.staff_user)
        self.client.get(url)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, HTTPStatus.NOT_FOUND)


class RegistrationCeremonyTests(PasskeyLoginMixin, TestCase):
    """Tests restricting passkey registration to sessions that may enrol one."""

    begin_url = reverse_lazy("staff:passkey_register")
    complete_url = reverse_lazy("staff:passkey_register_complete")

    @classmethod
    def setUpTestData(cls) -> None:
        """Set up test data."""
        super().setUpTestData()
        cls.staff_user = User.objects.create_user(
            username="staff", password=get_random_string(12), is_staff=True
        )
        cls.customer = User.objects.create_user(username="customer", password=get_random_string(12))

    def test_an_anonymous_visitor_cannot_begin_a_registration(self) -> None:
        """Test that an anonymous visitor cannot begin a registration."""
        response = self.client.get(self.begin_url)
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertEqual(response.json()["status"], "ERR")

    def test_a_customer_cannot_begin_a_registration(self) -> None:
        """Test that a signed-in customer cannot begin a registration."""
        self.client.force_login(self.customer)
        response = self.client.get(self.begin_url)
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_a_customer_cannot_complete_a_registration(self) -> None:
        """Test that a signed-in customer cannot complete a registration."""
        self.client.force_login(self.customer)
        response = self.client.post(self.complete_url)
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_a_staff_password_session_cannot_begin_a_registration(self) -> None:
        """Test that a staff session no passkey established cannot enrol a passkey."""
        self.client.force_login(self.staff_user)
        response = self.client.get(self.begin_url)
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_a_verified_admin_is_issued_registration_options(self) -> None:
        """Test that a verified admin is issued options excluding the passkey they hold."""
        passkey = self.passkey_login(self.staff_user)
        response = self.client.get(self.begin_url)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        options = response.json()["publicKey"]
        self.assertEqual(options["rp"]["id"], "localhost")
        self.assertEqual(
            [credential["id"] for credential in options["excludeCredentials"]],
            [passkey.credential_id],
        )

    def test_an_enrolment_session_is_issued_registration_options(self) -> None:
        """Test that a session an enrolment link granted is issued registration options."""
        self.client.get(enrolment_url(self.staff_user))
        response = self.client.get(self.begin_url)
        self.assertEqual(response.status_code, HTTPStatus.OK)
