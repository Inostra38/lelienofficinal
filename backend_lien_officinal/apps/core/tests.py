from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import Pharmacy
from apps.team.models import Collaborator


def make_pharmacy(email='pharma@test.com', password='testpass123'):
    p = Pharmacy.objects.create_user(email=email, password=password, nom_officine='Test')
    return p


def make_collab(pharmacy, can_manage_account=True, pin='1234', active=True):
    c = Collaborator(
        pharmacy=pharmacy,
        first_name='Test',
        last_name='Collab',
        role=Collaborator.Role.TITULAIRE,
        is_active=active,
    )
    c.set_pin(pin)
    c.save()
    return c


def auth_header(pharmacy):
    refresh = RefreshToken.for_user(pharmacy)
    return {'HTTP_AUTHORIZATION': f'Bearer {str(refresh.access_token)}'}


class AccountVerifySecurityAccessViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.pharmacy = make_pharmacy()
        self.collab = make_collab(self.pharmacy, can_manage_account=True, pin='4242')
        self.url = reverse('account-verify-security-access')
        self.headers = auth_header(self.pharmacy)

    def test_correct_pin_returns_200(self):
        response = self.client.post(
            self.url, {'confirmation_pin': '4242'}, **self.headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['valid'])

    def test_wrong_pin_returns_403(self):
        response = self.client.post(
            self.url, {'confirmation_pin': '0000'}, **self.headers
        )
        self.assertEqual(response.status_code, 403)

    def test_no_pin_returns_403(self):
        response = self.client.post(self.url, {}, **self.headers)
        self.assertEqual(response.status_code, 403)

    def test_no_authorized_collab_returns_403(self):
        """Aucun collaborateur avec can_manage_account → 403 sans exception."""
        self.collab.can_manage_account = False
        self.collab.save()
        response = self.client.post(
            self.url, {'confirmation_pin': '4242'}, **self.headers
        )
        self.assertEqual(response.status_code, 403)

    def test_multiple_collabs_all_iterated(self):
        """Avec plusieurs collabs, la boucle parcourt tous sans lever d'exception."""
        make_collab(self.pharmacy, can_manage_account=True, pin='9999')
        make_collab(self.pharmacy, can_manage_account=True, pin='8888')
        # PIN correct du troisième collab
        c3 = Collaborator(
            pharmacy=self.pharmacy,
            first_name='Third',
            last_name='Admin',
            role=Collaborator.Role.ADJOINT,
            is_active=True,
        )
        c3.set_pin('7777')
        c3.save()
        response = self.client.post(
            self.url, {'confirmation_pin': '7777'}, **self.headers
        )
        self.assertEqual(response.status_code, 200)
