"""Passkey ceremony views."""

from collections.abc import Callable
from functools import wraps
from http import HTTPStatus
from typing import Any

from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse
from passkeys import FIDO2

from passkeys_admin.conf import setting


def refused(message: str) -> dict[str, str]:
    """Return the JSON body the ceremony client expects for a refusal."""
    return {"status": "ERR", "message": message}


def rate_limited(view: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
    """Wrap a view so one client cannot start ceremonies faster than the rate."""

    @wraps(view)
    def inner(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        key = f"passkeys-admin-ceremony:{request.META.get('REMOTE_ADDR', '')}"
        cache.add(key, 0, setting("CEREMONY_WINDOW"))
        if cache.incr(key) > setting("CEREMONY_RATE"):
            return JsonResponse(
                refused("Too many attempts. Please wait and try again."),
                status=HTTPStatus.TOO_MANY_REQUESTS,
            )
        return view(request, *args, **kwargs)

    return inner


authentication_begin = rate_limited(FIDO2.auth_begin)
