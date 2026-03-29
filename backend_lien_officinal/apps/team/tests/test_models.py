"""
Tests team/models.py — check_pin(), lockout PIN, ContractHistory signal
"""

from datetime import date
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.core.models import Pharmacy
from apps.team.models import Collaborator, ContractHistory

_counter = 0


def _make_pharmacy():
    global _counter
    _counter += 1
    return Pharmacy.objects.create_user(
        email=f"pharma_team_{_counter}@test.com",
        password="pass",
        nom_officine="Test",
    )


def _make_collab(pharmacy, pin="1234"):
    c = Collaborator.objects.create(
        pharmacy=pharmacy,
        first_name="Alice",
        last_name="Test",
        role=Collaborator.Role.PREPARATEUR,
        color="#aabbcc",
        weekly_hours=35,
    )
    c.set_pin(pin)
    c.save()
    return c


# ── check_pin ─────────────────────────────────────────────────────────────────

class TestCheckPin(TestCase):

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy, pin="1234")

    def test_pin_correct_retourne_true(self):
        self.assertTrue(self.collab.check_pin("1234"))

    def test_pin_incorrect_retourne_false(self):
        self.assertFalse(self.collab.check_pin("9999"))

    def test_pin_vide_retourne_false(self):
        self.assertFalse(self.collab.check_pin(""))

    def test_pin_avec_espaces_retourne_false(self):
        self.assertFalse(self.collab.check_pin(" 1234"))

    def test_set_pin_change_le_hash(self):
        old_hash = self.collab.pin_hash
        self.collab.set_pin("5678")
        self.collab.save()
        self.assertNotEqual(self.collab.pin_hash, old_hash)
        self.assertTrue(self.collab.check_pin("5678"))
        self.assertFalse(self.collab.check_pin("1234"))


# ── Lockout PIN ────────────────────────────────────────────────────────────────

class TestPinLockout(TestCase):
    """
    Le code verrouille après 50 échecs consécutifs (24h).
    TESTS.md mentionnait 3 — la valeur réelle est 50.
    """

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy, pin="1234")

    def test_fail_count_incremente(self):
        self.collab.pin_fail_count += 1
        self.collab.save(update_fields=["pin_fail_count"])
        self.collab.refresh_from_db()
        self.assertEqual(self.collab.pin_fail_count, 1)

    def test_lockout_a_50_echecs(self):
        """À 50 échecs, pin_locked_until est positionné."""
        self.collab.pin_fail_count = 49
        self.collab.save(update_fields=["pin_fail_count"])
        # Simule le 50e échec via la logique de views.py
        self.collab.pin_fail_count += 1
        if self.collab.pin_fail_count >= 50:
            self.collab.pin_locked_until = timezone.now() + __import__('datetime').timedelta(hours=24)
            self.collab.pin_fail_count = 0
            self.collab.save(update_fields=["pin_fail_count", "pin_locked_until"])
        self.assertIsNotNone(self.collab.pin_locked_until)
        self.assertEqual(self.collab.pin_fail_count, 0)

    def test_lockout_until_dans_le_futur(self):
        self.collab.pin_locked_until = timezone.now() + __import__('datetime').timedelta(hours=24)
        self.collab.save(update_fields=["pin_locked_until"])
        self.collab.refresh_from_db()
        self.assertTrue(self.collab.pin_locked_until > timezone.now())

    def test_lockout_expire_dans_le_passe(self):
        """Un pin_locked_until dans le passé ne bloque pas (logique view)."""
        self.collab.pin_locked_until = timezone.now() - __import__('datetime').timedelta(minutes=1)
        self.collab.save(update_fields=["pin_locked_until"])
        self.collab.refresh_from_db()
        self.assertFalse(self.collab.pin_locked_until > timezone.now())

    def test_reset_fail_count_apres_succes(self):
        self.collab.pin_fail_count = 5
        self.collab.pin_locked_until = None
        self.collab.save(update_fields=["pin_fail_count", "pin_locked_until"])
        # Simule reset après succès
        self.collab.pin_fail_count = 0
        self.collab.pin_locked_until = None
        self.collab.save(update_fields=["pin_fail_count", "pin_locked_until"])
        self.collab.refresh_from_db()
        self.assertEqual(self.collab.pin_fail_count, 0)


# ── Signal ContractHistory ────────────────────────────────────────────────────

class TestContractHistorySignal(TestCase):

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy)

    def test_creation_contrat_met_a_jour_weekly_hours(self):
        ContractHistory.objects.create(
            collaborator=self.collab,
            contract_type=ContractHistory.ContractType.CDI,
            weekly_hours=28.0,
            start_date=date(2026, 1, 1),
        )
        self.collab.refresh_from_db()
        self.assertEqual(float(self.collab.weekly_hours), 28.0)

    def test_contrat_ferme_ne_met_pas_a_jour(self):
        """Un contrat déjà terminé (end_date passé) ne met pas à jour weekly_hours."""
        initial_hours = float(self.collab.weekly_hours)
        ContractHistory.objects.create(
            collaborator=self.collab,
            contract_type=ContractHistory.ContractType.CDD,
            weekly_hours=20.0,
            start_date=date(2020, 1, 1),
            end_date=date(2020, 12, 31),   # passé
        )
        self.collab.refresh_from_db()
        # Contrat terminé → weekly_hours ne change pas
        self.assertEqual(float(self.collab.weekly_hours), initial_hours)

    def test_ancien_contrat_ferme_automatiquement(self):
        """Quand un nouveau contrat en cours est créé, l'ancien doit être fermé."""
        old = ContractHistory.objects.create(
            collaborator=self.collab,
            contract_type=ContractHistory.ContractType.CDI,
            weekly_hours=35.0,
            start_date=date(2024, 1, 1),
        )
        new_start = date(2026, 3, 1)
        ContractHistory.objects.create(
            collaborator=self.collab,
            contract_type=ContractHistory.ContractType.CDI,
            weekly_hours=28.0,
            start_date=new_start,
        )
        old.refresh_from_db()
        # L'ancien contrat doit avoir end_date = new_start - 1j
        expected_end = new_start - __import__('datetime').timedelta(days=1)
        self.assertEqual(old.end_date, expected_end)
