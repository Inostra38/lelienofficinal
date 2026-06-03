import base64
import hashlib

from cryptography.fernet import Fernet, MultiFernet
from django.conf import settings


def _fernet_from(material: str) -> Fernet:
    """Dérive une clé Fernet 32 bytes (base64 urlsafe) depuis une chaîne via SHA-256."""
    digest = hashlib.sha256(material.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _primary_fernet() -> Fernet:
    """
    Clé de chiffrement courante, dérivée de ADMIN_TOTP_KEY (E1).
    Indépendante de SECRET_KEY : une fuite de SECRET_KEY ne permet plus de
    déchiffrer les secrets TOTP.
    """
    return _fernet_from(settings.ADMIN_TOTP_KEY)


def _legacy_fernet() -> Fernet | None:
    """
    Ancienne clé dérivée de SECRET_KEY (avant E1). Conservée UNIQUEMENT pour
    déchiffrer les secrets TOTP existants (rotation). Renvoyée None si la clé
    courante est déjà identique (cas où ADMIN_TOTP_KEY == SECRET_KEY).
    """
    if settings.ADMIN_TOTP_KEY == settings.SECRET_KEY:
        return None
    return _fernet_from(settings.SECRET_KEY)


def encrypt_totp_secret(secret: str) -> str:
    """Chiffre un secret TOTP (base32) avec la clé courante et retourne un token Fernet."""
    return _primary_fernet().encrypt(secret.encode()).decode()


def decrypt_totp_secret(token: str) -> str:
    """
    Déchiffre un token Fernet et retourne le secret TOTP original.
    Tente d'abord la clé courante, puis l'ancienne clé (legacy) pour les
    secrets chiffrés avant la séparation des clés. Les secrets legacy seront
    ré-chiffrés avec la clé courante au prochain setup TOTP.
    """
    fernets = [_primary_fernet()]
    legacy = _legacy_fernet()
    if legacy is not None:
        fernets.append(legacy)
    return MultiFernet(fernets).decrypt(token.encode()).decode()
