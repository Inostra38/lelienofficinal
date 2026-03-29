"""
Tests resources/models.py — Category unicité, suppression cascade
"""

from django.db import IntegrityError
from django.test import TestCase

from apps.core.models import Pharmacy
from apps.resources.models import Category, ResourceCard

_counter = 0


def _make_pharmacy():
    global _counter
    _counter += 1
    return Pharmacy.objects.create_user(
        email=f"pharma_rm_{_counter}@test.com",
        password="pass",
        nom_officine="Test",
    )


# ── Category — unicité (pharmacy, nom) ───────────────────────────────────────

class TestCategoryUniqueness(TestCase):

    def setUp(self):
        self.pharmacy = _make_pharmacy()

    def test_creation_category_simple(self):
        cat = Category.objects.create(nom="Médicaments", owner_pharmacy=self.pharmacy)
        self.assertEqual(cat.nom, "Médicaments")

    def test_doublon_meme_pharmacie_integrity_error(self):
        Category.objects.create(nom="Médicaments", owner_pharmacy=self.pharmacy)
        with self.assertRaises(IntegrityError):
            Category.objects.create(nom="Médicaments", owner_pharmacy=self.pharmacy)

    def test_meme_nom_pharmacies_differentes_ok(self):
        other = _make_pharmacy()
        Category.objects.create(nom="Médicaments", owner_pharmacy=self.pharmacy)
        # Pas d'exception pour une autre pharmacie
        cat2 = Category.objects.create(nom="Médicaments", owner_pharmacy=other)
        self.assertEqual(cat2.nom, "Médicaments")

    def test_noms_differents_meme_pharmacie_ok(self):
        Category.objects.create(nom="Médicaments", owner_pharmacy=self.pharmacy)
        cat2 = Category.objects.create(nom="Matériel", owner_pharmacy=self.pharmacy)
        self.assertEqual(Category.objects.filter(owner_pharmacy=self.pharmacy).count(), 2)


# ── Category — suppression cascade ───────────────────────────────────────────

class TestCategoryDeletion(TestCase):
    """
    Category a on_delete=CASCADE sur ResourceCard.
    Supprimer une Category supprime ses ResourceCards associées.
    """

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.cat = Category.objects.create(nom="Labo", owner_pharmacy=self.pharmacy)

    def test_suppression_category_supprime_cartes(self):
        """Les ResourceCards liées à une catégorie sont supprimées en cascade."""
        card = ResourceCard.objects.create(
            titre="Test Card",
            owner_pharmacy=self.pharmacy,
            category=self.cat,
            type='PRIVATE',
        )
        cat_pk = self.cat.pk
        self.cat.delete()
        self.assertFalse(Category.objects.filter(pk=cat_pk).exists())
        self.assertFalse(ResourceCard.objects.filter(pk=card.pk).exists())

    def test_suppression_category_sans_cartes_ok(self):
        cat_pk = self.cat.pk
        self.cat.delete()
        self.assertFalse(Category.objects.filter(pk=cat_pk).exists())
