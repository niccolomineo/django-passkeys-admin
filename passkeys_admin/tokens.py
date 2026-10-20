"""Passkey enrolment tokens."""

from typing import Any

from django.contrib.auth.base_user import AbstractBaseUser
from django.core import signing
from passkeys.models import UserPasskey

from passkeys_admin.conf import setting
from passkeys_admin.constants import ENROLMENT_SALT


def passkey_state(user: AbstractBaseUser) -> list[int]:
    """Return a value that changes whenever the user's set of passkeys changes."""
    return sorted(UserPasskey.objects.filter(user=user).values_list("pk", flat=True))


def login_state(user: AbstractBaseUser) -> str:
    """Return a value that changes every time the user logs in."""
    return user.last_login.isoformat() if user.last_login else ""


def make_enrolment_token(user: AbstractBaseUser) -> str:
    """Return a signed token authorising a single passkey enrolment."""
    return signing.dumps(
        {"user": user.pk, "state": passkey_state(user), "login": login_state(user)},
        salt=ENROLMENT_SALT,
    )


def read_enrolment_token(token: str) -> dict[str, Any] | None:
    """Return the payload of a valid, unexpired enrolment token, or None."""
    try:
        return signing.loads(token, salt=ENROLMENT_SALT, max_age=setting("ENROLMENT_MAX_AGE"))
    except signing.BadSignature:
        return None
