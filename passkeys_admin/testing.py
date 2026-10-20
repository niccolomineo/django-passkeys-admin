"""Test helpers for projects whose admin is passkey-only."""

from secrets import token_bytes

from cryptography.hazmat.primitives.asymmetric import ec
from django.contrib.auth.base_user import AbstractBaseUser
from fido2.cose import ES256
from fido2.utils import websafe_encode
from fido2.webauthn import AttestedCredentialData
from passkeys.models import UserPasskey

from passkeys_admin.constants import PASSKEY_SESSION_KEY


class PasskeyLoginMixin:
    """Test case mixin that logs the client in with a session a passkey established."""

    def create_passkey(self, user: AbstractBaseUser, name: str = "Test passkey") -> UserPasskey:
        """Create a passkey owned by the given user, holding a well-formed credential."""
        credential_id = token_bytes(32)
        public_key = ES256.from_cryptography_key(
            ec.generate_private_key(ec.SECP256R1()).public_key()
        )
        credential = AttestedCredentialData.create(bytes(16), credential_id, public_key)
        return UserPasskey.objects.create(
            user=user,
            name=name,
            credential_id=websafe_encode(credential_id),
            token=websafe_encode(credential),
        )

    def passkey_login(self, user: AbstractBaseUser, name: str = "Test passkey") -> UserPasskey:
        """Log the client in and mark the session as established by a passkey."""
        passkey = self.create_passkey(user, name=name)
        self.client.force_login(user)
        session = self.client.session
        session[PASSKEY_SESSION_KEY] = {"passkey": True, "id": passkey.pk}
        session.save()
        return passkey
