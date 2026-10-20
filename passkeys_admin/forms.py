"""Passkeys admin forms."""

from collections.abc import Iterable
from typing import Any

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.base_user import AbstractBaseUser
from django.core.exceptions import ValidationError
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from passkeys_admin.conf import setting


class PasskeyAuthenticationForm(forms.Form):
    """Login form accepting a passkey assertion and no other credential."""

    passkeys = forms.CharField(widget=forms.HiddenInput)

    error_messages = {"invalid": _("That passkey was not accepted. Please try again.")}

    def __init__(self, request: HttpRequest | None = None, *args: Any, **kwargs: Any) -> None:
        """Keep the request the assertion is read from."""
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self) -> dict[str, Any]:
        """Authenticate the submitted assertion and keep the resulting user."""
        cleaned_data = super().clean()
        if self.errors:
            return cleaned_data
        user = authenticate(self.request)
        if user is None:
            raise ValidationError(self.error_messages["invalid"], code="invalid")
        self.user_cache = user
        return cleaned_data

    def get_user(self) -> AbstractBaseUser | None:
        """Return the user the submitted passkey authenticated."""
        return self.user_cache


class PasskeyOnlyPasswordResetMixin:
    """Withhold password resets from accounts that must use a passkey."""

    def get_users(self, email: str) -> Iterable[AbstractBaseUser]:
        """Return only those users still allowed to authenticate with a password."""
        users = super().get_users(email)
        if not setting("REQUIRED"):
            return users
        return (user for user in users if not user.is_staff)
