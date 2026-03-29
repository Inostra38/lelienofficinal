import base64
import hashlib

from cryptography.fernet import Fernet
from django.conf import settings


def _get_fernet() -> Fernet:
    """
    Dérive une clé Fernet 32 bytes depuis SECRET_KEY via SHA-256.
    Déterministe : même SECRET_KEY → même clé de chiffrement.
    """
    digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_totp_secret(secret: str) -> str:
    """Chiffre un secret TOTP (base32) et retourne un token Fernet (str)."""
    return _get_fernet().encrypt(secret.encode()).decode()


def decrypt_totp_secret(token: str) -> str:
    """Déchiffre un token Fernet et retourne le secret TOTP original."""
    return _get_fernet().decrypt(token.encode()).decode()
