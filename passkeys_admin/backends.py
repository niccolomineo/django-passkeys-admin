"""Passkeys admin authentication backend."""

from typing import Any

from django.contrib.auth.base_user import AbstractBaseUser
from django.http import HttpRequest
from passkeys.backend import PasskeyModelBackend

from passkeys_admin.conf import setting
from passkeys_admin.constants import PASSKEY_SESSION_KEY


class PasskeyOnlyStaffBackend(PasskeyModelBackend):
    """Authenticate staff by passkey and everyone else by password, never both."""

    def authenticate(
        self, request: HttpRequest | None, **credentials: Any
    ) -> AbstractBaseUser | None:
        """Return the authenticated user, leaving no passkey mark when refusing."""
        user = super().authenticate(request, **credentials)
        if self.may_authenticate(user, bool(credentials.get("password"))):
            return user
        if request is not None:
            request.session.pop(PASSKEY_SESSION_KEY, None)
        return None

    def may_authenticate(self, user: AbstractBaseUser | None, with_password: bool) -> bool:
        """Return True when this user may sign in the way they have just tried."""
        if user is None or not self.user_can_authenticate(user):
            return False
        if not setting("REQUIRED"):
            return True
        if with_password:
            return not user.is_staff
        return user.is_staff
