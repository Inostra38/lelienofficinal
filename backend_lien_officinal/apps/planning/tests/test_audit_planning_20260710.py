"""Planning : atomicité + autorisations contraintes (audit 2026-07-09).

Q01 — BulkShiftUpdateView supprimait les shifts existants PUIS pouvait sortir en
      400 au milieu de la création → perte de planning. Désormais : validation
      complète avant toute suppression, puis delete+create atomiques.
S08 — ConstraintsView.post sans contrôle can_manage_planning.
S11 — ConstraintDetailView.patch sans contrôle ni protection des contraintes
      réglementaires.
"""
import datetime

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.core.models import Pharmacy
from apps.planning.models import Constraint, ConstraintSet, Shift
from apps.team.models import Collaborator

_n = 0


def _pharma():
    global _n
    _n += 1
    return Pharmacy.objects.create_user(email=f"pl_{_n}@t.com", password="x", nom_officine="Ph")


def _pharma_client(p):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(p).access_token}")
    return c


def _collab(pharmacy, **perms):
    c = Collaborator.objects.create(
        pharmacy=pharmacy, first_name="A", last_name="B",
        role=Collaborator.Role.PREPARATEUR, color="#112233", weekly_hours=35, **perms,
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


class TestBulkShiftAtomicity(TestCase):
    def test_echec_en_cours_de_lot_ne_detruit_pas_lexistant(self):
        pharma = _pharma()
        collab = _collab(pharma)
        jour = timezone.now().date()
        # shift existant à préserver si le lot échoue
        existant = Shift.objects.create(
            collaborator=collab,
            start_datetime=timezone.make_aware(datetime.datetime.combine(jour, datetime.time(9, 0))),
            end_datetime=timezone.make_aware(datetime.datetime.combine(jour, datetime.time(12, 0))),
        )
        # lot : un item valide + un item avec collaborateur inexistant
        payload = [
            {'collaborator_id': collab.id, 'date': jour.isoformat(), 'start': '14:00', 'end': '18:00'},
            {'collaborator_id': 999999, 'date': jour.isoformat(), 'start': '14:00', 'end': '18:00'},
        ]
        resp = _pharma_client(pharma).post(
            '/api/planning/templates/A/apply-bulk/', payload, format='json',
        )
        self.assertEqual(resp.status_code, 400)
        # le shift existant NE doit PAS avoir été supprimé
        self.assertTrue(Shift.objects.filter(id=existant.id).exists())
        # et aucun nouveau shift n'a été créé (tout ou rien)
        self.assertEqual(Shift.objects.filter(collaborator__pharmacy=pharma).count(), 1)


class TestConstraintAuthz(TestCase):
    def test_prepa_sans_droit_ne_peut_pas_creer_contrainte(self):
        pharma = _pharma()
        prepa = _collab(pharma)  # pas de can_manage_planning
        resp = _collab_client(pharma, prepa).post(
            '/api/planning/constraints/',
            {'level': 'pharmacy', 'description': 'biais'}, format='json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_manager_peut_creer_contrainte(self):
        pharma = _pharma()
        manager = _collab(pharma, can_manage_planning=True)
        resp = _collab_client(pharma, manager).post(
            '/api/planning/constraints/',
            {'level': 'pharmacy', 'description': 'ok'}, format='json',
        )
        self.assertIn(resp.status_code, (200, 201))

    def test_contrainte_reglementaire_non_modifiable(self):
        pharma = _pharma()
        cs = ConstraintSet.objects.create(pharmacy=pharma)
        regle = Constraint.objects.create(
            constraint_set=cs, level=Constraint.Level.REGULATORY,
            description="11h de repos", is_active=True,
        )
        # même le jeton pharmacie de base (droits titulaire) ne doit pas
        # pouvoir désactiver une contrainte réglementaire
        resp = _pharma_client(pharma).patch(
            f'/api/planning/constraints/{regle.id}/', {'is_active': False}, format='json',
        )
        self.assertEqual(resp.status_code, 403)
        regle.refresh_from_db()
        self.assertTrue(regle.is_active)

    def test_prepa_sans_droit_ne_peut_pas_patcher_contrainte(self):
        pharma = _pharma()
        cs = ConstraintSet.objects.create(pharmacy=pharma)
        c = Constraint.objects.create(
            constraint_set=cs, level=Constraint.Level.PHARMACY, description="x",
        )
        prepa = _collab(pharma)
        resp = _collab_client(pharma, prepa).patch(
            f'/api/planning/constraints/{c.id}/', {'description': 'modif'}, format='json',
        )
        self.assertEqual(resp.status_code, 403)
