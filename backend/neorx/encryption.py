"""Versioned field encryption using PyCA primitives; no plaintext fallback."""
import base64
import unicodedata
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

PREFIX = "neorx$1$"


class DecryptionError(ValueError):
    """A stored value cannot be authenticated with the configured key."""


def key_bytes():
    value = getattr(settings, "FERNET_KEY", None)
    try:
        if not isinstance(value, str) or not value:
            raise ValueError
        Fernet(value.encode("ascii"))
        return value.encode("ascii")
    except (ValueError, TypeError, UnicodeError):
        raise ImproperlyConfigured("FERNET_KEY válida es obligatoria; no hay fallback sin cifrado.") from None


def encrypt_text(value):
    return PREFIX + Fernet(key_bytes()).encrypt(str(value).encode("utf-8")).decode("ascii")


def decrypt_text(value):
    if not isinstance(value, str) or not value.startswith(PREFIX):
        raise DecryptionError("Valor almacenado sin formato de cifrado válido.")
    try:
        return Fernet(key_bytes()).decrypt(value[len(PREFIX):].encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeError, ValueError):
        raise DecryptionError("No se pudo autenticar el dato cifrado.") from None


def normalize_ci(value):
    return "".join(unicodedata.normalize("NFKC", str(value)).upper().split())


def ci_digest(value):
    source = base64.urlsafe_b64decode(key_bytes())
    index_key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
                     info=b"neorx:ci-search-index:v1").derive(source)
    signer = hmac.HMAC(index_key, hashes.SHA256())
    signer.update(normalize_ci(value).encode("utf-8"))
    return signer.finalize().hex()
