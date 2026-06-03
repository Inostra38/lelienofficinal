"""
Validation centralisée des fichiers uploadés (M3).

Avant, seul le panel admin validait type + taille ; les uploads côté pharmacie
(ressources, qualité) acceptaient n'importe quel fichier → SVG/HTML malveillant
(XSS stocké si servi inline), déni de service disque.

L'allowlist exclut volontairement image/svg+xml et text/html, qui peuvent
embarquer du JavaScript.
"""
from django.core.exceptions import ValidationError

# Documents + images web courantes.
ALLOWED_UPLOAD_TYPES = {
    'application/pdf',
    'image/jpeg', 'image/png', 'image/webp', 'image/gif',
}
ALLOWED_UPLOAD_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'webp', 'gif'}

# Sous-ensemble images uniquement (endpoints d'images).
ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'gif'}

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 Mo


def validate_upload(uploaded, *, allowed_types=None, allowed_extensions=None,
                    max_size=MAX_UPLOAD_SIZE):
    """
    Valide un fichier uploadé (type MIME déclaré + extension + taille).
    Lève django.core.exceptions.ValidationError si invalide.
    No-op si `uploaded` est None (champ optionnel).

    Le content_type étant déclaré par le client, on vérifie AUSSI l'extension :
    un fichier doit satisfaire les deux allowlists pour passer.
    """
    if uploaded is None:
        return

    types = allowed_types or ALLOWED_UPLOAD_TYPES
    extensions = allowed_extensions or ALLOWED_UPLOAD_EXTENSIONS

    content_type = getattr(uploaded, 'content_type', None)
    if content_type not in types:
        raise ValidationError("Type de fichier non autorisé.")

    name = getattr(uploaded, 'name', '') or ''
    ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
    if ext not in extensions:
        raise ValidationError("Extension de fichier non autorisée.")

    if uploaded.size > max_size:
        raise ValidationError(
            f"Fichier trop volumineux (max {max_size // (1024 * 1024)} Mo)."
        )
