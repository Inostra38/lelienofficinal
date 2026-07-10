"""Messagerie & Tâches — isolation inter-clients + réapparition (audit 2026-07-09).

Q08/Q10 — ces deux apps n'avaient aucun test dédié ; l'isolation reposait sur
          _get_conversation_for_participant et les contrôles collaborateur sans
          filet. On couvre les invariants critiques manquants.
Q07     — une conversation masquée réapparaît quand un message arrive via HTTP
          (cohérence avec le chemin WebSocket).
"""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.core.models import Pharmacy
from apps.messaging.models import Conversation
from apps.tasks.models import Task
from apps.team.models import Collaborator

_n = 0


def _pharma():
    global _n
    _n += 1
    return Pharmacy.objects.create_user(email=f"mt_{_n}@t.com", password="x", nom_officine="Ph")


def _collab(pharmacy, name="A"):
    c = Collaborator.objects.create(
        pharmacy=pharmacy, first_name=name, last_name="X",
        role=Collaborator.Role.PREPARATEUR, color="#112233", weekly_hours=35,
    )
    c.set_pin("1234")
    c.save()
    return c


def _collab_client(pharmacy, collaborator):
    token = AccessToken.for_user(pharmacy)
    token['auth_type'] = 'collaborator'
    token['collaborator_id'] = collaborator.id
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


class TestMessagingIsolation(TestCase):
    def setUp(self):
        self.pha = _pharma()
        self.alice = _collab(self.pha, "Alice")
        self.bob = _collab(self.pha, "Bob")
        self.conv = Conversation.objects.create(
            pharmacy=self.pha, created_by=self.alice, subject="Sujet",
        )
        self.conv.participants.add(self.alice, self.bob)

    def test_envoi_message_par_autre_pharmacie_404(self):
        autre = _pharma()
        intrus = _collab(autre, "Intrus")
        resp = _collab_client(autre, intrus).post(
            f'/api/messaging/conversations/{self.conv.id}/messages/',
            {'content': 'coucou'}, format='json',
        )
        self.assertEqual(resp.status_code, 404)

    def test_non_participant_meme_pharmacie_404(self):
        carol = _collab(self.pha, "Carol")  # même pharmacie mais pas participante
        resp = _collab_client(self.pha, carol).post(
            f'/api/messaging/conversations/{self.conv.id}/messages/',
            {'content': 'coucou'}, format='json',
        )
        self.assertEqual(resp.status_code, 404)

    def test_message_http_fait_reapparaitre_conversation_masquee(self):
        # Q07 : Bob masque la conversation, Alice envoie un message via HTTP →
        # la conversation réapparaît (hidden_by vidé).
        self.conv.hidden_by.add(self.bob)
        self.assertEqual(self.conv.hidden_by.count(), 1)
        resp = _collab_client(self.pha, self.alice).post(
            f'/api/messaging/conversations/{self.conv.id}/messages/',
            {'content': 'nouveau'}, format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.conv.refresh_from_db()
        self.assertEqual(self.conv.hidden_by.count(), 0)


class TestTasksIsolation(TestCase):
    def test_get_tache_autre_pharmacie_404(self):
        pha = _pharma()
        auteur = _collab(pha, "Auteur")
        task = Task.objects.create(pharmacy=pha, title="Tâche", created_by=auteur)

        autre = _pharma()
        intrus = _collab(autre, "Intrus")
        resp = _collab_client(autre, intrus).get(f'/api/tasks/{task.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_liste_taches_ne_voit_pas_autre_pharmacie(self):
        pha_a = _pharma()
        a = _collab(pha_a, "A")
        Task.objects.create(pharmacy=pha_a, title="Tâche A", created_by=a)

        pha_b = _pharma()
        b = _collab(pha_b, "B")
        resp = _collab_client(pha_b, b).get('/api/tasks/')
        self.assertEqual(resp.status_code, 200)
        blob = str(resp.data)
        self.assertNotIn("Tâche A", blob)
