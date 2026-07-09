"""Non-régression sur les 3 IDOR/RGPD critiques confirmés (audit 2026-07-09).

F-004 — resources/views.py wizard_complete : adoption d'une carte PRIVATE d'une
        autre officine → fuite au dashboard. Corrigé par un filtre de type.
F-003 — quality/serializers.py ProcedureDetailSerializer : pilot_ids/category_ids/
        group non bornés → un collaborateur d'une autre officine attachable, nom
        relu. Corrigé par bornage des querysets à la pharmacie de la requête.
F-001 — core/account_deletion.py : Shift/AbsenceRequest orphelinés au lieu d'être
        effacés → données RH sensibles conservées après suppression RGPD.
"""
import datetime

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import Pharmacy
from apps.core.account_deletion import execute_account_deletion
from apps.planning.models import Shift, AbsenceRequest
from apps.quality.models import Procedure
from apps.resources.models import ResourceCard, ResourceItem, PharmacyPreference
from apps.team.models import Collaborator

_n = 0


def _pharma():
    global _n
    _n += 1
    return Pharmacy.objects.create_user(email=f"audit_{_n}@t.com", password="x", nom_officine="Ph")


def _client(p):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(p).access_token}")
    return c


def _collab(pharmacy, **kw):
    c = Collaborator.objects.create(
        pharmacy=pharmacy, first_name=kw.pop('first_name', 'Alice'),
        last_name=kw.pop('last_name', 'Martin'), role=Collaborator.Role.PREPARATEUR,
        color="#112233", weekly_hours=35, **kw,
    )
    c.set_pin("1234")
    c.save()
    return c


class TestF004WizardAdoption(TestCase):
    """wizard_complete ne doit adopter que des cartes partagées."""

    def test_carte_privee_dautre_officine_non_adoptable(self):
        victime = _pharma()
        secrete = ResourceCard.objects.create(
            owner_pharmacy=victime, type='PRIVATE',
            titre="Contrat CONFIDENTIEL", description_officielle="Remise 12%",
        )
        ResourceItem.objects.create(card=secrete, label="Tel", url="0600000000", ordre=0)

        attaquant = _pharma()
        cli = _client(attaquant)
        resp = cli.post('/api/wizard/complete/', {
            'pharmacy': {}, 'selected_categories': ['Grossistes'],
            'classified_resources': [{'resource_id': secrete.id, 'category': 'Grossistes'}],
            'collaborators': [],
        }, format='json')

        self.assertEqual(resp.status_code, 200)  # la carte est ignorée, pas d'erreur
        self.assertFalse(
            PharmacyPreference.objects.filter(pharmacy=attaquant, card=secrete).exists(),
            "La carte PRIVATE d'une autre officine ne doit pas être adoptée.",
        )
        blob = str(cli.get('/api/categories/').data)
        self.assertNotIn("CONFIDENTIEL", blob)
        self.assertNotIn("0600000000", blob)

    def test_carte_officielle_reste_adoptable(self):
        officielle = ResourceCard.objects.create(
            type='OFFICIAL', titre="Ordre national", description_officielle="Public",
        )
        pharma = _pharma()
        cli = _client(pharma)
        resp = cli.post('/api/wizard/complete/', {
            'pharmacy': {}, 'selected_categories': ['Officiel'],
            'classified_resources': [{'resource_id': officielle.id, 'category': 'Officiel'}],
            'collaborators': [],
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            PharmacyPreference.objects.filter(pharmacy=pharma, card=officielle).exists(),
            "L'adoption d'une carte OFFICIAL légitime doit continuer de fonctionner.",
        )


class TestF003ProcedurePilots(TestCase):
    """ProcedureDetailSerializer ne doit accepter que des cibles de la pharmacie."""

    def _patch_pilots(self, pharmacy, procedure, pilot_id):
        # JWT pharmacie de base = droits titulaire implicites (permissions.py)
        return _client(pharmacy).patch(
            f'/api/quality/procedures/{procedure.id}/',
            {'pilot_ids': [pilot_id]}, format='json',
        )

    def test_pilote_dautre_officine_rejete(self):
        victime = _pharma()
        collab_b = _collab(victime, first_name="Secret", last_name="Salarié")

        attaquant = _pharma()
        proc = Procedure.objects.create(pharmacy=attaquant, title="Ma procédure")

        resp = self._patch_pilots(attaquant, proc, collab_b.id)
        self.assertEqual(resp.status_code, 400)
        proc.refresh_from_db()
        self.assertNotIn(collab_b, proc.pilots.all())
        # et le nom du salarié de B ne fuite pas dans la réponse
        self.assertNotIn("Secret", str(resp.data))

    def test_pilote_de_sa_propre_officine_accepte(self):
        pharma = _pharma()
        mon_collab = _collab(pharma, first_name="Bob", last_name="Interne")
        proc = Procedure.objects.create(pharmacy=pharma, title="Ma procédure")

        resp = self._patch_pilots(pharma, proc, mon_collab.id)
        self.assertEqual(resp.status_code, 200)
        proc.refresh_from_db()
        self.assertIn(mon_collab, proc.pilots.all())


class TestF001AccountDeletionRGPD(TestCase):
    """La suppression de compte doit effacer les Shift/AbsenceRequest sensibles."""

    def test_shift_et_absence_effaces(self):
        pharma = _pharma()
        collab = _collab(pharma, first_name="Jean", last_name="Dupont")

        now = timezone.now()
        Shift.objects.create(
            collaborator=collab, collaborator_snapshot="Jean Dupont",
            start_datetime=now, end_datetime=now + datetime.timedelta(hours=7),
            is_absent=True, absence_type='maladie', note="arrêt maladie",
        )
        AbsenceRequest.objects.create(
            collaborator=collab, start_date=now.date(), end_date=now.date(),
            type='maladie', note="certificat médical",
        )

        # témoin : une autre officine ne doit pas être touchée
        autre = _pharma()
        autre_collab = _collab(autre)
        Shift.objects.create(
            collaborator=autre_collab, start_datetime=now,
            end_datetime=now + datetime.timedelta(hours=7),
        )

        self.assertTrue(execute_account_deletion(pharma.id))

        self.assertFalse(
            Shift.objects.filter(collaborator_snapshot="Jean Dupont").exists(),
            "Le shift avec données de santé doit être effacé, pas orpheliné.",
        )
        self.assertEqual(
            Shift.objects.filter(collaborator__isnull=True, absence_type='maladie').count(), 0,
            "Aucun shift 'maladie' orphelin (collaborator=NULL) ne doit subsister.",
        )
        self.assertFalse(
            AbsenceRequest.objects.filter(note="certificat médical").exists(),
            "La demande d'absence maladie doit être effacée.",
        )
        # non-régression : l'autre officine est intacte
        self.assertEqual(Shift.objects.filter(collaborator__pharmacy=autre).count(), 1)
