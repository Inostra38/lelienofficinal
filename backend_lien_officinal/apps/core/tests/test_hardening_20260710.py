"""Durcissement (audit 2026-07-09).

S17 — le logo pharmacie ne passait par aucune validation d'upload → un SVG/HTML
      (vecteur XSS) pouvait être stocké. Désormais validé (allowlist image).
Q03 — la route de la pub d'inactivité était une URL absolue collée dans path()
      → injoignable. Route corrigée en /api/ads/inactivity/.
"""
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import Pharmacy

_n = 0


def _real_png() -> bytes:
    """Vrai PNG valide (Pillow), pour que l'ImageField ne le rejette pas lui-même
    et qu'on teste bien la validation S17, pas la validation d'image de Django."""
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (2, 2), (0, 128, 0)).save(buf, 'PNG')
    return buf.getvalue()


def _pharma():
    global _n
    _n += 1
    return Pharmacy.objects.create_user(email=f"hard_{_n}@t.com", password="x", nom_officine="Ph")


def _client(p):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(p).access_token}")
    return c


class TestLogoUploadValidation(TestCase):
    URL = '/api/pharmacy/me/update/'

    def test_svg_refuse(self):
        svg = SimpleUploadedFile(
            'evil.svg', b'<svg onload="alert(1)"></svg>', content_type='image/svg+xml',
        )
        resp = _client(_pharma()).patch(self.URL, {'logo': svg}, format='multipart')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('logo', resp.data)

    def test_html_deguise_en_png_refuse(self):
        # bon content_type déclaré mais mauvaise extension → rejeté (double check)
        f = SimpleUploadedFile('x.html', b'<script>alert(1)</script>', content_type='image/png')
        resp = _client(_pharma()).patch(self.URL, {'logo': f}, format='multipart')
        self.assertEqual(resp.status_code, 400)

    def test_png_valide_accepte(self):
        png = SimpleUploadedFile('logo.png', _real_png(), content_type='image/png')
        resp = _client(_pharma()).patch(self.URL, {'logo': png}, format='multipart')
        # 200 attendu ; en tout cas PAS un rejet lié au logo
        self.assertNotEqual(resp.status_code, 400)


class TestInactivityAdRoute(TestCase):
    def test_route_resout_vers_chemin_propre(self):
        # Q03 : la route doit résoudre vers /api/ads/inactivity/ (et non une URL
        # absolue collée dans path()).
        self.assertEqual(reverse('inactivity-ad'), '/api/ads/inactivity/')
