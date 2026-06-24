"""Tests du service promo : validation, redemption, unicité, quota."""
from django.test import TestCase

from apps.billing.models import PromoCode, PromoRedemption
from apps.billing.promo_service import (
    PromoError,
    get_pharmacy_promo,
    validate_and_redeem,
)
from apps.billing.tests.utils import make_pharmacy


class ValidateAndRedeemTests(TestCase):
    def setUp(self):
        self.pharmacy = make_pharmacy()
        self.promo = PromoCode.objects.create(code='GIPHAR3', months_free=3)

    def test_redeem_success_case_insensitive(self):
        result = validate_and_redeem('giphar3', self.pharmacy)  # casse différente
        self.assertEqual(result.code, 'GIPHAR3')
        self.promo.refresh_from_db()
        self.assertEqual(self.promo.current_uses, 1)
        self.assertTrue(
            PromoRedemption.objects.filter(
                promo_code=self.promo, pharmacy=self.pharmacy
            ).exists()
        )

    def test_unknown_code_raises(self):
        with self.assertRaises(PromoError):
            validate_and_redeem('NOPE', self.pharmacy)

    def test_inactive_code_raises(self):
        self.promo.is_active = False
        self.promo.save()
        with self.assertRaises(PromoError):
            validate_and_redeem('GIPHAR3', self.pharmacy)

    def test_already_used_raises_and_does_not_double_count(self):
        validate_and_redeem('GIPHAR3', self.pharmacy)
        with self.assertRaises(PromoError):
            validate_and_redeem('GIPHAR3', self.pharmacy)
        self.promo.refresh_from_db()
        self.assertEqual(self.promo.current_uses, 1)
        self.assertEqual(
            PromoRedemption.objects.filter(pharmacy=self.pharmacy).count(), 1
        )

    def test_quota_reached_raises(self):
        self.promo.max_uses = 1
        self.promo.current_uses = 1
        self.promo.save()
        with self.assertRaises(PromoError):
            validate_and_redeem('GIPHAR3', self.pharmacy)

    def test_different_pharmacies_can_use_same_code(self):
        other = make_pharmacy()
        validate_and_redeem('GIPHAR3', self.pharmacy)
        validate_and_redeem('GIPHAR3', other)
        self.promo.refresh_from_db()
        self.assertEqual(self.promo.current_uses, 2)


class GetPharmacyPromoTests(TestCase):
    def test_returns_none_without_redemption(self):
        pharmacy = make_pharmacy()
        self.assertIsNone(get_pharmacy_promo(pharmacy))

    def test_returns_redeemed_code(self):
        pharmacy = make_pharmacy()
        PromoCode.objects.create(code='GIPHAR3', months_free=3)
        validate_and_redeem('GIPHAR3', pharmacy)
        self.assertEqual(get_pharmacy_promo(pharmacy).code, 'GIPHAR3')
