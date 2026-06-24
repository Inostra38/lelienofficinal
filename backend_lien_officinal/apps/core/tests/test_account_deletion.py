"""Tests du service d'anonymisation de compte (apps/core/account_deletion.py)."""
from decimal import Decimal

from django.test import TestCase

from apps.core.account_deletion import execute_account_deletion
from apps.core.models import Pharmacy, SMSTemplate
from apps.billing.models import Invoice, SmsCreditTransaction
from apps.billing.tests.utils import make_pharmacy


class ExecuteAccountDeletionTests(TestCase):

    def test_anonymizes_pii_and_disables_login(self):
        p = make_pharmacy(
            siret='12345678901234', city='Paris', phone='0102030405',
            address1='1 rue Test', vat_number='FR123', email_verified=True,
        )
        self.assertTrue(execute_account_deletion(p.id))

        p.refresh_from_db()
        self.assertEqual(p.email, f'deleted-{p.id}@deleted.invalid')
        self.assertEqual(p.nom_officine, f'Pharmacie supprimée #{p.id}')
        self.assertIsNone(p.siret)
        self.assertEqual(p.city, '')
        self.assertEqual(p.phone, '')
        self.assertEqual(p.vat_number, '')
        self.assertFalse(p.email_verified)
        self.assertFalse(p.is_active)
        self.assertFalse(p.has_usable_password())
        self.assertIsNotNone(p.anonymized_at)

    def test_keeps_invoices(self):
        p = make_pharmacy()
        Invoice.objects.create(
            pharmacy=p, invoice_type='subscription',
            invoice_number='LLO-2026-000123',
            amount_ht=Decimal('39'), amount_ttc=Decimal('46.80'),
        )
        execute_account_deletion(p.id)
        # La pharmacie survit (PROTECT) et la facture est conservée.
        self.assertTrue(Pharmacy.objects.filter(pk=p.id).exists())
        self.assertEqual(Invoice.objects.filter(pharmacy=p).count(), 1)

    def test_erases_non_billing_data(self):
        p = make_pharmacy()
        SMSTemplate.objects.create(pharmacy=p, title='Rappel', content='Bonjour')
        # (des templates par défaut sont auto-créés en plus du nôtre)
        self.assertTrue(SMSTemplate.objects.filter(pharmacy=p).exists())

        execute_account_deletion(p.id)
        self.assertEqual(SMSTemplate.objects.filter(pharmacy=p).count(), 0)

    def test_nonconformity_protect_is_handled(self):
        """NonConformity protège Procedure (PROTECT) : la suppression ne doit
        pas lever ProtectedError, et les deux doivent disparaître."""
        from apps.quality.models import Procedure, NonConformity
        p = make_pharmacy()
        proc = Procedure.objects.create(pharmacy=p, title='Procédure test')
        NonConformity.objects.create(
            pharmacy=p, title='NC', description='desc',
            severity=NonConformity.Severity.values[0], procedure=proc,
        )

        # Ne doit pas lever ProtectedError.
        self.assertTrue(execute_account_deletion(p.id))
        self.assertEqual(Procedure.objects.filter(pharmacy=p).count(), 0)
        self.assertEqual(NonConformity.objects.filter(pharmacy=p).count(), 0)

    def test_sms_credits_forfeited_and_logged(self):
        p = make_pharmacy(sms_credits=50)
        execute_account_deletion(p.id)

        p.refresh_from_db()
        self.assertEqual(p.sms_credits, 0)
        tx = SmsCreditTransaction.objects.filter(
            pharmacy=p, reason=SmsCreditTransaction.Reason.CLOSURE,
        ).first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.delta, -50)

    def test_idempotent(self):
        p = make_pharmacy()
        self.assertTrue(execute_account_deletion(p.id))
        # Deuxième passage : aucune action, pas d'erreur.
        self.assertFalse(execute_account_deletion(p.id))

    def test_missing_pharmacy_returns_false(self):
        self.assertFalse(execute_account_deletion(999999))
