"""WebSocket SMS — handshake sous-protocole (audit 2026-07-09, même bug que tasks).

Le jeton passe en sous-protocole ['bearer', <jwt>] et le consumer l'échote.
"""
import jwt
from django.conf import settings
from django.test import TransactionTestCase
from channels.testing import WebsocketCommunicator

from backend_lien_officinal.asgi import application
from apps.core.models import Pharmacy
from apps.team.models import Collaborator

_n = 0


class SmsWSHandshakeTests(TransactionTestCase):
    def setUp(self):
        global _n
        _n += 1
        self.pharmacy = Pharmacy.objects.create_user(
            email=f"wssms_{_n}@t.com", password="x", nom_officine="Ph",
        )
        self.collab = Collaborator.objects.create(
            pharmacy=self.pharmacy, first_name="S", last_name="M",
            role=Collaborator.Role.PREPARATEUR, color="#112233", weekly_hours=35,
        )
        self.collab.set_pin("1234")
        self.collab.save()
        self.token = jwt.encode(
            {'auth_type': 'collaborator', 'collaborator_id': self.collab.id},
            settings.SECRET_KEY, algorithm='HS256',
        )

    async def test_sous_protocole_connecte(self):
        comm = WebsocketCommunicator(
            application, "/ws/sms/status/",
            headers=[(b"origin", b"http://localhost")],
            subprotocols=["bearer", self.token],
        )
        connected, subprotocol = await comm.connect()
        self.assertTrue(connected)
        self.assertEqual(subprotocol, "bearer")
        await comm.disconnect()

    async def test_sans_sous_protocole_refuse(self):
        comm = WebsocketCommunicator(
            application, "/ws/sms/status/",
            headers=[(b"origin", b"http://localhost")],
        )
        connected, _ = await comm.connect()
        self.assertFalse(connected)
        await comm.disconnect()
