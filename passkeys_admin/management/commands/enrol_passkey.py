"""Print a single-use link a staff user can follow to enrol a passkey."""

from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.urls import reverse

from passkeys_admin.conf import setting
from passkeys_admin.tokens import make_enrolment_token

User = get_user_model()


class Command(BaseCommand):
    """Print a single-use passkey enrolment link for a staff user."""

    help = "Print a single-use link a staff user can follow to enrol a passkey."

    def add_arguments(self, parser: CommandParser) -> None:
        """Add the command arguments."""
        parser.add_argument("username", help=f"The staff user's {User.USERNAME_FIELD}.")
        parser.add_argument("--base-url", required=True, help="Origin to prefix the link with.")

    def handle(self, *args: Any, **options: Any) -> None:
        """Print the enrolment link for the requested staff user."""
        username = options["username"]
        user = User._default_manager.filter(
            **{User.USERNAME_FIELD: username}, is_staff=True, is_active=True
        ).first()
        if user is None:
            raise CommandError(f"No active staff user found with {User.USERNAME_FIELD} {username}.")
        path = reverse("admin:passkey_enrol", kwargs={"token": make_enrolment_token(user)})
        minutes = setting("ENROLMENT_MAX_AGE") // 60
        self.stdout.write(
            f"Single-use passkey enrolment link, valid for {minutes} minutes "
            "and void as soon as it is followed:"
        )
        self.stdout.write(f"{options['base_url'].rstrip('/')}{path}")
