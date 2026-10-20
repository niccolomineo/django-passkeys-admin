"""Passkeys admin settings, each read from the project with a default."""

from typing import Any

from django.conf import settings

DEFAULTS: dict[str, Any] = {
    "REQUIRED": True,
    "ENROLMENT_MAX_AGE": 900,
    "CEREMONY_RATE": 30,
    "CEREMONY_WINDOW": 60,
}


def setting(name: str) -> Any:
    """Return the project's ``PASSKEYS_ADMIN_<name>`` setting, or its default."""
    return getattr(settings, f"PASSKEYS_ADMIN_{name}", DEFAULTS[name])
