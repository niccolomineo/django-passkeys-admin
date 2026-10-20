"""Passkeys admin application configuration."""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PasskeysAdminConfig(AppConfig):
    """Passkeys admin application configuration."""

    name = "passkeys_admin"
    verbose_name = _("Passkeys admin")
