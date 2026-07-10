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
from apps.planning.models import Constraint, ConstraintSet, Shift, TimeAdjustment
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
    global _n
    _n += 1
    c = Collaborator.objects.create(
        pharmacy=pharmacy, first_name=f"C{_n}", last_name="X",
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


class TestTimeAdjustmentDeleteAuthz(TestCase):
    """S10 — « ses propres ajustements » = ceux qu'il a déclarés (declared_by)."""

    def _adj(self, pharmacy, collaborator, declared_by):
        return TimeAdjustment.objects.create(
            collaborator=collaborator, declared_by=declared_by,
            date=timezone.now().date(), type=TimeAdjustment.Type.OVERTIME,
            actual_time=datetime.time(19, 0), reference_time=datetime.time(18, 0),
            duration_minutes=60,
        )

    def test_sujet_non_declarant_ne_peut_pas_supprimer(self):
        pharma = _pharma()
        manager = _collab(pharma, can_manage_planning=True)
        salarie = _collab(pharma)
        # le manager a saisi un ajustement AU SUJET du salarié
        adj = self._adj(pharma, collaborator=salarie, declared_by=manager)
        resp = _collab_client(pharma, salarie).delete(f'/api/planning/adjustments/{adj.id}/')
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(TimeAdjustment.objects.filter(id=adj.id).exists())

    def test_declarant_peut_supprimer_le_sien(self):
        pharma = _pharma()
        salarie = _collab(pharma)
        adj = self._adj(pharma, collaborator=salarie, declared_by=salarie)
        resp = _collab_client(pharma, salarie).delete(f'/api/planning/adjustments/{adj.id}/')
        self.assertEqual(resp.status_code, 204)

    def test_manager_peut_tout_supprimer(self):
        pharma = _pharma()
        manager = _collab(pharma, can_manage_planning=True)
        salarie = _collab(pharma)
        adj = self._adj(pharma, collaborator=salarie, declared_by=salarie)
        resp = _collab_client(pharma, manager).delete(f'/api/planning/adjustments/{adj.id}/')
        self.assertEqual(resp.status_code, 204)
