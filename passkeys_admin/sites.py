"""Passkeys admin site."""

from collections.abc import Callable
from functools import update_wrapper
from http import HTTPStatus
from typing import Any

from django.contrib import admin, messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.views import redirect_to_login
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse
from django.template.response import TemplateResponse
from django.urls import URLPattern, URLResolver, path, reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from passkeys import FIDO2
from passkeys.models import UserPasskey

from passkeys_admin.conf import setting
from passkeys_admin.constants import BACKEND, ENROLMENT_SESSION_KEY, PASSKEY_SESSION_KEY
from passkeys_admin.forms import PasskeyAuthenticationForm
from passkeys_admin.tokens import login_state, passkey_state, read_enrolment_token
from passkeys_admin.views import authentication_begin, refused

User = get_user_model()

View = Callable[..., HttpResponse]


class PasskeyAdminMixin:
    """Turn an admin site into a passkey-only one with credential management."""

    passkeys_template = "passkeys_admin/passkeys.html"

    @property
    def login_template(self) -> str | None:
        """Return the passkey login page, or nothing where passkeys are optional."""
        return "passkeys_admin/login.html" if setting("REQUIRED") else None

    @property
    def login_form(self) -> type[PasskeyAuthenticationForm] | None:
        """Return the passkey login form, or nothing where passkeys are optional."""
        return PasskeyAuthenticationForm if setting("REQUIRED") else None

    def passkey_verified(self, request: HttpRequest) -> bool:
        """Return True when a passkey that still exists established this session."""
        if not hasattr(request, "passkey_verified"):
            request.passkey_verified = self.check_passkey(request)
        return request.passkey_verified

    def check_passkey(self, request: HttpRequest) -> bool:
        """Look up whether the passkey that established this session still exists."""
        passkey = request.session.get(PASSKEY_SESSION_KEY) or {}
        if not passkey.get("passkey"):
            return False
        return UserPasskey.objects.filter(
            pk=passkey.get("id"), user=request.user, enabled=True
        ).exists()

    def has_permission(self, request: HttpRequest) -> bool:
        """Return True for active staff, verified by a passkey where required."""
        if not super().has_permission(request):
            return False
        return not setting("REQUIRED") or self.passkey_verified(request)

    def can_enrol_passkey(self, request: HttpRequest) -> bool:
        """Return True for a verified admin or for a live enrolment session."""
        return self.has_permission(request) or (
            request.user.is_active
            and request.user.is_staff
            and request.session.get(ENROLMENT_SESSION_KEY, False)
        )

    def enrolment_view(self, view: View) -> View:
        """Wrap a page so verified admins and enrolment sessions may both reach it."""

        def inner(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            if not self.can_enrol_passkey(request):
                return redirect_to_login(
                    request.get_full_path(),
                    reverse("admin:login", current_app=self.name),
                )
            return view(request, *args, **kwargs)

        inner = never_cache(inner)
        inner = csrf_protect(inner)
        return update_wrapper(inner, view)

    def registration_view(self, view: View) -> View:
        """Wrap a registration ceremony so only those who may enrol can start it."""

        def inner(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            if not self.can_enrol_passkey(request):
                return JsonResponse(
                    refused("Sign in with a passkey or an enrolment link first."),
                    status=HTTPStatus.FORBIDDEN,
                )
            return view(request, *args, **kwargs)

        return update_wrapper(inner, view)

    def get_urls(self) -> list[URLPattern | URLResolver]:
        """Return admin URL patterns including passkey management and ceremonies."""
        return [
            path("passkeys/", self.enrolment_view(self.passkeys_view), name="passkeys"),
            path(
                "passkeys/delete/<int:pk>/",
                self.admin_view(require_POST(self.passkey_delete_view)),
                name="passkey_delete",
            ),
            path("passkeys/enrol/<str:token>/", self.passkey_enrol_view, name="passkey_enrol"),
            path("passkeys/authenticate/", authentication_begin, name="passkey_authenticate"),
            path(
                "passkeys/register/",
                self.registration_view(FIDO2.reg_begin),
                name="passkey_register",
            ),
            path(
                "passkeys/register/complete/",
                self.registration_view(FIDO2.reg_complete),
                name="passkey_register_complete",
            ),
            *super().get_urls(),
        ]

    def passkeys_view(self, request: HttpRequest) -> HttpResponse:
        """Display the current user's passkeys and allow enrolling another."""
        context = {
            **self.each_context(request),
            "title": _("Passkeys"),
            "subtitle": None,
            "can_delete": self.has_permission(request),
            "passkeys": UserPasskey.objects.filter(user=request.user).order_by("added_on"),
        }
        return TemplateResponse(request, self.passkeys_template, context)

    def passkey_delete_view(self, request: HttpRequest, pk: int) -> HttpResponse:
        """Delete one of the current user's passkeys, keeping the last one."""
        passkeys = UserPasskey.objects.filter(user=request.user)
        passkey = passkeys.filter(pk=pk).first()
        if passkey is None:
            messages.error(request, _("That passkey could not be found."))
        elif passkeys.count() <= 1:
            messages.error(request, _("Your last remaining passkey cannot be deleted."))
        else:
            passkey.delete()
            messages.success(request, _("The passkey has been deleted."))
        return HttpResponseRedirect(reverse("admin:passkeys", current_app=self.name))

    def get_enrolment_user(self, token: str) -> AbstractBaseUser | None:
        """Return the active staff user a still-unused enrolment token refers to."""
        payload = read_enrolment_token(token)
        if payload is None:
            return None
        user = User._default_manager.filter(
            pk=payload["user"], is_staff=True, is_active=True
        ).first()
        if user is None:
            return None
        if passkey_state(user) != payload["state"]:
            return None
        if login_state(user) != payload["login"]:
            return None
        return user

    @method_decorator(never_cache)
    def passkey_enrol_view(self, request: HttpRequest, token: str) -> HttpResponse:
        """Log a staff user in from a single-use link so they can enrol a passkey."""
        user = self.get_enrolment_user(token)
        if user is None:
            raise Http404
        login(request, user, backend=BACKEND)
        request.session[ENROLMENT_SESSION_KEY] = True
        request.session.set_expiry(setting("ENROLMENT_MAX_AGE"))
        return HttpResponseRedirect(reverse("admin:passkeys", current_app=self.name))


class PasskeyAdminSite(PasskeyAdminMixin, admin.AdminSite):
    """A passkey-only admin site, ready to stand in for the default one."""
