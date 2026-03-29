"""
Intégration : flux onboarding complet
Register → Créer collaborateur → Login PIN collaborateur
"""

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import Pharmacy
from apps.team.models import Collaborator

_counter = 0


def _pharmacy_client(pharmacy):
    client = APIClient()
    refresh = RefreshToken.for_user(pharmacy)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


class TestFluxOnboardingComplet(TestCase):
    """
    Flux complet :
    1. Register → 201 + JWT
    2. Créer un collaborateur via l'API équipe
    3. Login PIN du collaborateur → JWT collaborateur
    """

    def test_register_puis_collab_puis_login(self):
        """Flux complet : Register → collab → PIN login."""
        # 1. Register
        resp_register = self.client.post(
            '/api/auth/register/',
            {
                'email': 'onboarding_flux@test.com',
                'password': 'SecurePass123!',
                'password_confirm': 'SecurePass123!',
                'nom_officine': 'Pharmacie Flux',
            },
            format='json',
        )
        self.assertEqual(resp_register.status_code, 201)
        self.assertIn('access', resp_register.data)
        self.assertIn('refresh_token', resp_register.cookies)

        # Récupérer la pharmacie créée
        pharmacy = Pharmacy.objects.get(email='onboarding_flux@test.com')
        client = _pharmacy_client(pharmacy)

        # 2. Créer un collaborateur
        resp_collab = client.post(
            '/api/team/',
            {
                'first_name': 'Bob',
                'last_name': 'Onboarding',
                'role': Collaborator.Role.PREPARATEUR,
                'color': '#aabbcc',
                'weekly_hours': 35,
                'pin': '1234',
            },
            format='json',
        )
        self.assertIn(resp_collab.status_code, [200, 201])
        # CollaboratorCreateSerializer n'expose pas 'id' → récupérer depuis la DB
        collab = Collaborator.objects.get(pharmacy=pharmacy, first_name='Bob')
        collab_id = collab.id
        self.assertEqual(collab.first_name, 'Bob')
        self.assertEqual(collab.pharmacy, pharmacy)

        # 3. Login PIN → JWT collaborateur
        resp_login = client.post(
            '/api/team/login/',
            {
                'collaborator_id': collab_id,
                'pin_code': '1234',
            },
            format='json',
        )
        self.assertEqual(resp_login.status_code, 200)
        self.assertIn('access', resp_login.data)
        self.assertIn('session_info', resp_login.cookies)
        self.assertEqual(resp_login.data['collaborator_id'], collab_id)

    def test_register_email_deja_utilise(self):
        """Deuxième register avec le même email → 400."""
        payload = {
            'email': 'doublon_flux@test.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'nom_officine': 'Pharmacie Doublon',
        }
        self.client.post('/api/auth/register/', payload, format='json')
        resp = self.client.post('/api/auth/register/', payload, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_login_mauvais_pin(self):
        """Mauvais PIN → 403."""
        pharmacy = Pharmacy.objects.create_user(
            email='pharma_badpin@test.com',
            password='pass',
            nom_officine='Test',
        )
        collab = Collaborator.objects.create(
            pharmacy=pharmacy,
            first_name='Charlie',
            last_name='Badpin',
            role=Collaborator.Role.PREPARATEUR,
            color='#112233',
            weekly_hours=35,
        )
        collab.set_pin('9999')
        collab.save()

        client = _pharmacy_client(pharmacy)
        resp = client.post(
            '/api/team/login/',
            {'collaborator_id': collab.id, 'pin_code': '0000'},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_collab_sans_token_401(self):
        """Créer un collaborateur sans token → 401."""
        resp = self.client.post(
            '/api/team/',
            {
                'first_name': 'Eve',
                'last_name': 'Unauth',
                'role': Collaborator.Role.PREPARATEUR,
                'color': '#001122',
                'weekly_hours': 35,
                'pin_code': '5678',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 401)
