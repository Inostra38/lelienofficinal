class ContentSecurityPolicyMiddleware:
    """
    Ajoute le header Content-Security-Policy sur toutes les réponses.
    Policy stricte mais compatible Angular + Tailwind + Quill + images inline.
    """

    CSP_POLICY = "; ".join([
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline' https://js.stripe.com",  # Angular inline + Stripe.js
        "style-src 'self' 'unsafe-inline'",            # Tailwind + Quill injectent des styles inline
        "img-src 'self' data: blob: https://*.scw.cloud", # QR codes base64, blob URLs, S3 images
        "font-src 'self' data:",                       # Fonts inline (base64)
        "connect-src 'self' https://*.scw.cloud https://api.stripe.com",  # API + Scaleway S3 + Stripe
        "frame-src https://js.stripe.com https://hooks.stripe.com",  # iframes Stripe Elements / 3DS / SEPA
        "frame-ancestors 'none'",                      # Équivalent X-Frame-Options DENY
        "base-uri 'self'",
        "form-action 'self'",
        "object-src 'none'",                           # Bloque Flash, Java applets
        "upgrade-insecure-requests",
    ])

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # Ne pas écraser si déjà défini (ex: Django admin)
        if 'Content-Security-Policy' not in response:
            response['Content-Security-Policy'] = self.CSP_POLICY
        return response
