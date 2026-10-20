<img src="https://raw.githubusercontent.com/niccolomineo/django-passkeys-admin/main/icon.png" alt="django-passkeys-admin" width="128">

# django-passkeys-admin

[![PyPI](https://img.shields.io/pypi/v/django-passkeys-admin?label=pypi)](https://pypi.org/project/django-passkeys-admin/)
[![Python](https://img.shields.io/pypi/pyversions/django-passkeys-admin?label=python)](https://pypi.org/project/django-passkeys-admin/)
[![Django](https://img.shields.io/pypi/frameworkversions/django/django-passkeys-admin?label=django)](https://pypi.org/project/django-passkeys-admin/)
[![CI](https://github.com/niccolomineo/django-passkeys-admin/actions/workflows/ci.yml/badge.svg)](https://github.com/niccolomineo/django-passkeys-admin/actions/workflows/ci.yml)
[![License](https://img.shields.io/pypi/l/django-passkeys-admin?label=license)](LICENSE)

A **passkey-only Django admin**: staff sign in with a passkey and nothing else,
while every other account keeps its password. Built on
[django-passkeys](https://github.com/mkalioby/django-passkeys).

Requires Python 3.12 or newer and Django 5.2 LTS or newer. Every supported
combination — Python 3.12/3.13/3.14 against Django 5.2/6.0/6.1 — is exercised
by the test suite on every push.

## The gap this fills

django-passkeys provides the WebAuthn ceremonies and an authentication backend
that accepts **a password or a passkey**. Pointing `LOGIN_URL` at a passkey page
changes which form staff see; it does not change which credential the backend
accepts, so a staff password keeps working everywhere it worked before.
django-otp-webauthn adds a passkey as a second factor, and django-allauth is a
whole account system. None of them takes passwords away from the admin.

This package does, and it covers what going passwordless then requires:

| Guarantee | How it holds |
| --- | --- |
| **Passkey only, for staff only** | The backend refuses a staff account its own correct password, and refuses a passkey to anyone who is not staff. |
| **The session lasts as long as the passkey** | Every admin request checks that the passkey which opened the session still exists and is enabled. Deleting a passkey shuts out every session it opened. |
| **The first passkey** | A passwordless admin cannot be entered to enrol the first passkey. `manage.py enrol_passkey` prints a signed, single-use link that grants a short session able to do exactly that and nothing else. |
| **No way back in through a reset** | A password reset form mixin withholds resets from staff accounts. |
| **Never the last passkey** | The management page refuses to delete the last passkey an account holds. |
| **Rate limited** | Starting an authentication ceremony is limited per client address. |

## Installation

```bash
pip install django-passkeys-admin
```

Add both apps, the backend and the settings django-passkeys needs:

```python
INSTALLED_APPS = [
    ...
    "passkeys",
    "passkeys_admin",
]

AUTHENTICATION_BACKENDS = ["passkeys_admin.backends.PasskeyOnlyStaffBackend"]

FIDO_SERVER_ID = "example.com"
FIDO_SERVER_NAME = "Example"
PASSKEYS_ALLOW_NO_PASSKEY_FIELD = True
```

`FIDO_SERVER_ID` is the WebAuthn relying party: the domain the admin is served
from, with no scheme or port. `PASSKEYS_ALLOW_NO_PASSKEY_FIELD` makes the
django-passkeys backend return nothing, rather than raise, when it is handed a
request carrying neither a password nor a passkey — which any other login form
in the project will eventually do.

Run the migrations, which create the django-passkeys table:

```bash
python manage.py migrate
```

Then make the admin site passkey-only. Either replace the default site:

```python
# yourproject/apps.py
from django.contrib.admin.apps import AdminConfig


class PasskeyAdminConfig(AdminConfig):
    default_site = "passkeys_admin.sites.PasskeyAdminSite"
```

```python
INSTALLED_APPS = [
    "yourproject.apps.PasskeyAdminConfig",  # in place of "django.contrib.admin"
    ...,
]
```

or mix it into the site you already have:

```python
from django.contrib import admin

from passkeys_admin.sites import PasskeyAdminMixin


class AdminSite(PasskeyAdminMixin, admin.AdminSite): ...
```

The passkey pages and the ceremony endpoints are the site's own URLs, under
`passkeys/`, so there is nothing to add to `urlpatterns`. **Do not include
`passkeys.urls`**: its views let any signed-in account register a passkey and
delete or disable its last one, which is what this package exists to prevent.

## The first passkey

Nobody can sign in to a passkey-only admin before they have a passkey, so the
first one is enrolled from a link:

```bash
python manage.py enrol_passkey alice --base-url https://example.com
```

The argument is whatever the user model's `USERNAME_FIELD` holds. The link is
valid for fifteen minutes and void as soon as it is followed, or as soon as the
account's passkeys change. It signs the user in to the passkey page alone: the
rest of the admin stays closed until they sign in with the passkey they have
just enrolled.

## Usage

### Linking the passkey page

Each staff member manages their passkeys at `admin/passkeys/`. To put it beside
the other user links, override `userlinks` in your `admin/base_site.html`:

```django
{% block userlinks %}
  <a href='{% url "admin:passkeys" %}'>{% translate "Passkeys" %}</a> /
  {{ block.super }}
{% endblock userlinks %}
```

### Password resets

Mix `PasskeyOnlyPasswordResetMixin` into every password reset form the project
offers. Without it, a staff account could still be handed a password it has no
use for in the admin, but that every other password login would accept.

```python
from django.contrib.auth.forms import PasswordResetForm

from passkeys_admin.forms import PasskeyOnlyPasswordResetMixin


class ResetForm(PasskeyOnlyPasswordResetMixin, PasswordResetForm):
    pass
```

### Tests

A test that reaches the admin needs a session a passkey opened. `force_login()`
no longer is one, so the package ships a mixin that is:

```python
from django.test import TestCase

from passkeys_admin.testing import PasskeyLoginMixin


class DashboardTests(PasskeyLoginMixin, TestCase):
    def test_the_index_loads(self):
        self.passkey_login(self.staff_user)
        ...
```

## Settings

| Setting | Default | |
| --- | --- | --- |
| `PASSKEYS_ADMIN_REQUIRED` | `True` | `False` restores password logins for staff, for a development machine whose origin is not the deployed one. |
| `PASSKEYS_ADMIN_ENROLMENT_MAX_AGE` | `900` | Seconds an enrolment link, and the session it grants, stays valid. |
| `PASSKEYS_ADMIN_CEREMONY_RATE` | `30` | Authentication ceremonies one client address may start per window. |
| `PASSKEYS_ADMIN_CEREMONY_WINDOW` | `60` | Length of that window, in seconds. |

## Notes

- **Browsers.** The ceremonies parse their options with
  `PublicKeyCredential.parseCreationOptionsFromJSON()` and
  `parseRequestOptionsFromJSON()`, which every browser has shipped since Safari
  18.4 (Chrome and Edge 129, Firefox 119). The browser's answer is serialised
  field by field rather than with `toJSON()`, which some password manager
  extensions replace with an implementation that drops fields or throws.
- **Behind a proxy**, the rate limit counts `REMOTE_ADDR`, and the address there
  is the proxy's unless the server is told to trust its forwarding header —
  `--forwarded-allow-ips` for gunicorn and uvicorn. Otherwise every client
  shares one counter. The rate also needs a cache shared by the workers: with
  the default per-process cache, the effective rate is the configured one times
  the number of workers.
- **Manifest static storage.** django-passkeys ships
  `bootstrap-toggle.min.js` with a `sourceMappingURL` to a map it does not ship,
  which `ManifestStaticFilesStorage` refuses at `collectstatic`. This package
  uses none of django-passkeys' static files, but `collectstatic` collects them
  all the same.
- **One admin site.** `enrol_passkey` reverses the link through the `admin`
  namespace, which resolves to the site named `admin`, or to the only one there
  is.

## License

MIT — see [LICENSE](LICENSE).
