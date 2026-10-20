"""Passkeys admin signal receivers, connected as Django loads the app's models."""

from typing import Any

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.http import HttpRequest

from passkeys_admin.constants import ENROLMENT_SESSION_KEY


@receiver(user_logged_in)
def end_enrolment_grant(
    sender: type, request: HttpRequest | None, user: AbstractBaseUser, **kwargs: Any
) -> None:
    """Drop the enrolment grant and its short expiry once a real login replaces it."""
    if request is None or not request.session.pop(ENROLMENT_SESSION_KEY, False):
        return
    request.session.set_expiry(None)
