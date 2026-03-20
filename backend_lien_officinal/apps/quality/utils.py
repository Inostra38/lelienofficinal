import bleach

ALLOWED_TAGS = [
    'p', 'br', 'strong', 'em', 'u', 's',
    'h1', 'h2', 'h3',
    'ul', 'ol', 'li',
    'a', 'img',
    'blockquote', 'pre', 'code',
    'span',
]

ALLOWED_ATTRIBUTES = {
    'a':    ['href', 'target'],
    'img':  ['src', 'alt'],
    'span': ['class'],
}


def sanitize_quill_html(html: str) -> str:
    """Nettoie le HTML produit par Quill : supprime tout ce qui n'est pas autorisé."""
    if not html:
        return ''
    return bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True,
    )
