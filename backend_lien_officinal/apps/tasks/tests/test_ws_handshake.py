"""WebSocket tâches — handshake (audit 2026-07-09).

S18/S19/Q09 — le jeton passe désormais en sous-protocole (pas en query string),
              le middleware l'y lit, et TaskConsumer échote 'bearer'.
S22         — AllowedHostsOriginValidator rejette une origine hors ALLOWED_HOSTS.

Exerce toute la pile ASGI (validateur d'origine + JWTAuthMiddleware + consumer)
via WebsocketCommunicator, sans serveur.
"""
import jwt
from django.conf import settings
from django.test import TransactionTestCase
from channels.testing import WebsocketCommunicator

from backend_lien_officinal.asgi import application
from apps.core.models import Pharmacy
from apps.team.models import Collaborator

_n = 0


def _collab_token(collaborator):
    return jwt.encode(
        {'auth_type': 'collaborator', 'collaborator_id': collaborator.id},
        settings.SECRET_KEY, algorithm='HS256',
    )


class TaskWSHandshakeTests(TransactionTestCase):
    def setUp(self):
        global _n
        _n += 1
        self.pharmacy = Pharmacy.objects.create_user(
            email=f"ws_{_n}@t.com", password="x", nom_officine="Ph",
        )
        self.collab = Collaborator.objects.create(
            pharmacy=self.pharmacy, first_name="Ws", last_name="User",
            role=Collaborator.Role.PREPARATEUR, color="#112233", weekly_hours=35,
        )
        self.collab.set_pin("1234")
        self.collab.save()
        self.token = _collab_token(self.collab)

    def _comm(self, subprotocols=None, origin=b"http://localhost"):
        headers = [(b"origin", origin)] if origin else []
        return WebsocketCommunicator(
            application, "/ws/tasks/", headers=headers, subprotocols=subprotocols,
        )

    async def test_sous_protocole_bearer_valide_connecte(self):
        comm = self._comm(subprotocols=["bearer", self.token])
        connected, subprotocol = await comm.connect()
        self.assertTrue(connected)
        self.assertEqual(subprotocol, "bearer")  # Q09 : sous-protocole échoté
        await comm.disconnect()

    async def test_jeton_invalide_refuse(self):
        comm = self._comm(subprotocols=["bearer", "jeton-bidon"])
        connected, _ = await comm.connect()
        self.assertFalse(connected)  # collaborator=None → close 4001
        await comm.disconnect()

    async def test_sans_sous_protocole_refuse(self):
        comm = self._comm(subprotocols=None)
        connected, _ = await comm.connect()
        self.assertFalse(connected)  # le middleware ne trouve pas le jeton
        await comm.disconnect()

    async def test_origine_interdite_refuse(self):
        # S22 : origine hors ALLOWED_HOSTS → rejetée avant même le middleware.
        comm = self._comm(subprotocols=["bearer", self.token], origin=b"http://evil.example.com")
        connected, _ = await comm.connect()
        self.assertFalse(connected)
        await comm.disconnect()
