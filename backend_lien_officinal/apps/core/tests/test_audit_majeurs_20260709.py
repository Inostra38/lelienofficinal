"""Non-régression sur les 3 IDOR majeurs multi-tenant confirmés (audit 2026-07-09).

Même famille que F-003/F-004 : une FK non bornée dans un serializer, ou un *_id
assigné en brut dans une action custom.

MT10 — resources ResourceCardViewSet : pas de perform_update → PATCH rattache la
       carte à la catégorie d'une autre officine.
MT09 — resources ResourceItemSerializer : champ card non borné → item rattaché à
       la carte d'une autre officine (défense en profondeur : l'affichage filtre
       déjà par owner, mais la référence croisée ne doit pas être créable).
MT08 — quality ProcedureViewSet.reorder : group_id/parent_id assignés en brut sans
       contrôle d'appartenance (court-circuite le bornage du serializer).
"""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import Pharmacy
from apps.quality.models import Procedure, ProcedureGroup
from apps.resources.models import Category, ResourceCard, ResourceItem

_n = 0


def _pharma():
    global _n
    _n += 1
    return Pharmacy.objects.create_user(email=f"maj_{_n}@t.com", password="x", nom_officine="Ph")


def _client(p):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(p).access_token}")
    return c


class TestMT10CardCategoryReassign(TestCase):
    """PATCH /api/cards/{id}/ ne doit pas accepter la catégorie d'une autre officine."""

    def test_categorie_dautre_officine_rejetee(self):
        attaquant = _pharma()
        ma_carte = ResourceCard.objects.create(
            owner_pharmacy=attaquant, type='PRIVATE', titre="Ma carte",
        )
        victime = _pharma()
        cat_b = Category.objects.create(owner_pharmacy=victime, nom="Cat B", ordre=0)

        resp = _client(attaquant).patch(
            f'/api/cards/{ma_carte.id}/', {'category': cat_b.id}, format='json'
        )
        self.assertEqual(resp.status_code, 400)
        ma_carte.refresh_from_db()
        self.assertIsNone(ma_carte.category_id)

    def test_categorie_propre_acceptee(self):
        pharma = _pharma()
        carte = ResourceCard.objects.create(owner_pharmacy=pharma, type='PRIVATE', titre="Carte")
        ma_cat = Category.objects.create(owner_pharmacy=pharma, nom="Ma cat", ordre=0)

        resp = _client(pharma).patch(
            f'/api/cards/{carte.id}/', {'category': ma_cat.id}, format='json'
        )
        self.assertEqual(resp.status_code, 200)
        carte.refresh_from_db()
        self.assertEqual(carte.category_id, ma_cat.id)


class TestMT09ItemCardBinding(TestCase):
    """POST /api/items/ ne doit pas rattacher un item à la carte d'une autre officine."""

    def test_item_sur_carte_dautre_officine_rejete(self):
        victime = _pharma()
        carte_b = ResourceCard.objects.create(
            owner_pharmacy=victime, type='PRIVATE', titre="Carte B",
        )
        attaquant = _pharma()
        resp = _client(attaquant).post('/api/items/', {
            'type': 'WEB', 'label': 'injection', 'url': 'http://x', 'card': carte_b.id,
        })
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(ResourceItem.objects.filter(card=carte_b, owner=attaquant).exists())

    def test_item_sur_sa_propre_carte_accepte(self):
        pharma = _pharma()
        carte = ResourceCard.objects.create(owner_pharmacy=pharma, type='PRIVATE', titre="Carte")
        resp = _client(pharma).post('/api/items/', {
            'type': 'WEB', 'label': 'ok', 'url': 'http://x', 'card': carte.id,
        })
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(ResourceItem.objects.filter(card=carte, owner=pharma).exists())


class TestMT08ProcedureReorderGroup(TestCase):
    """PATCH /api/quality/procedures/reorder/ ne doit pas accepter un group_id étranger."""

    def _reorder(self, pharmacy, payload):
        return _client(pharmacy).patch('/api/quality/procedures/reorder/', payload, format='json')

    def test_group_id_dautre_officine_rejete(self):
        victime = _pharma()
        groupe_b = ProcedureGroup.objects.create(pharmacy=victime, name="Groupe B")

        attaquant = _pharma()
        proc = Procedure.objects.create(pharmacy=attaquant, title="Ma procédure")

        resp = self._reorder(attaquant, [{'id': proc.id, 'position': 0, 'group_id': groupe_b.id}])
        self.assertEqual(resp.status_code, 403)
        proc.refresh_from_db()
        self.assertIsNone(proc.group_id)

    def test_parent_id_dautre_officine_rejete(self):
        victime = _pharma()
        parent_b = Procedure.objects.create(pharmacy=victime, title="Parent B")

        attaquant = _pharma()
        proc = Procedure.objects.create(pharmacy=attaquant, title="Ma procédure")

        resp = self._reorder(attaquant, [{'id': proc.id, 'position': 0, 'parent_id': parent_b.id}])
        self.assertEqual(resp.status_code, 403)
        proc.refresh_from_db()
        self.assertIsNone(proc.parent_id)

    def test_group_id_propre_accepte(self):
        pharma = _pharma()
        mon_groupe = ProcedureGroup.objects.create(pharmacy=pharma, name="Mon groupe")
        proc = Procedure.objects.create(pharmacy=pharma, title="Ma procédure")

        resp = self._reorder(pharma, [{'id': proc.id, 'position': 1, 'group_id': mon_groupe.id}])
        self.assertEqual(resp.status_code, 200)
        proc.refresh_from_db()
        self.assertEqual(proc.group_id, mon_groupe.id)
        self.assertEqual(proc.position, 1)
