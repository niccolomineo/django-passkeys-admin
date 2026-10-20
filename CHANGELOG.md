# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-20

### Added

- `PasskeyOnlyStaffBackend`, extending django-passkeys' backend so that a staff account authenticates with a passkey alone and every other account with a password alone. The upstream backend accepts either credential from anyone, so pointing `LOGIN_URL` at a passkey page left a staff password valid everywhere it was valid before.
- `PasskeyAdminMixin` and `PasskeyAdminSite`, which make an admin site passkey-only: a login page offering a passkey and no password field, and a permission check that every request repeats against the database, so deleting or disabling a passkey shuts out every session it opened rather than waiting for them to expire.
- A passkey management page, refusing to delete the last passkey an account holds, since that would lock the account out of an admin no password can open.
- The authentication and registration ceremonies wired into the admin site's own URLs, so installing the package adds nothing to `urlpatterns`. Registration is open only to a session a passkey opened or an enrolment link granted. A staff session opened any other way — by another backend the project uses, say — would otherwise enrol a passkey of its choosing and then use it to walk into the admin.
- `manage.py enrol_passkey`, printing a signed link that grants a short session able to enrol a first passkey and do nothing else. A passwordless admin has no other way in for an account with no passkey yet. The link is void once followed, once the account's passkeys change and after `PASSKEYS_ADMIN_ENROLMENT_MAX_AGE` seconds; the session it grants expires with it, and a real login lifts that expiry. The account is looked up by the user model's `USERNAME_FIELD`.
- `PasskeyOnlyPasswordResetMixin`, withholding password resets from staff accounts, which would otherwise be handed a password every other login in the project accepts.
- A per-address rate limit on starting an authentication ceremony, counted with `cache.add` and `cache.incr`, which the cache serialises, so two simultaneous requests cannot read the same count.
- Ceremony JavaScript that depends on no script of django-passkeys'. Options are parsed with the browser's own `parseCreationOptionsFromJSON()` and `parseRequestOptionsFromJSON()`; the answer is serialised field by field, because `toJSON()` is what some password manager extensions replace with an implementation that drops fields or throws.
- `PASSKEYS_ADMIN_*` settings, each with a default, so a project declares only what it changes.
- `passkeys_admin.testing.PasskeyLoginMixin`, logging a test client in with a session a passkey opened, which `force_login()` can no longer stand in for.
- A PEP 561 `py.typed` marker.
