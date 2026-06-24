from django.db import models


class Subscription(models.Model):
    """Abonnement Stripe d'une pharmacie."""

    class Plan(models.TextChoices):
        SMALL = 'small', 'Small (< 10 collaborateurs)'
        LARGE = 'large', 'Large (≥ 10 collaborateurs)'

    class Status(models.TextChoices):
        TRIALING  = 'trialing',  'Période d\'essai'
        ACTIVE    = 'active',    'Actif'
        PAST_DUE  = 'past_due',  'Paiement en retard'
        SUSPENDED = 'suspended', 'Suspendu'
        CANCELED  = 'canceled',  'Résilié'

    pharmacy               = models.OneToOneField(
                                 'core.Pharmacy',
                                 on_delete=models.PROTECT,
                                 related_name='subscription'
                             )
    stripe_customer_id     = models.CharField(max_length=255, unique=True, null=True, blank=True)
    stripe_subscription_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    plan                   = models.CharField(max_length=10, choices=Plan.choices, default=Plan.SMALL)
    status                 = models.CharField(max_length=20, choices=Status.choices, default=Status.TRIALING)
    trial_ends_at          = models.DateTimeField(null=True, blank=True)
    current_period_end     = models.DateTimeField(null=True, blank=True)
    suspended_at           = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end   = models.BooleanField(default=False)
    created_at             = models.DateTimeField(auto_now_add=True)
    updated_at             = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Abonnement'
        verbose_name_plural = 'Abonnements'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(plan__in=['small', 'large']),
                name='billing_subscription_plan_valid'
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=['trialing', 'active', 'past_due', 'suspended', 'canceled']),
                name='billing_subscription_status_valid'
            ),
        ]
        indexes = [
            models.Index(fields=['status'], name='bill_sub_status_idx'),
            models.Index(fields=['trial_ends_at'], name='bill_sub_trial_idx'),
            models.Index(fields=['current_period_end'], name='bill_sub_period_idx'),
        ]

    def __str__(self):
        return f"{self.pharmacy} — {self.get_plan_display()} ({self.get_status_display()})"

    @property
    def is_access_allowed(self):
        """Renvoie True si la pharmacie a accès à la plateforme."""
        return self.status in (self.Status.TRIALING, self.Status.ACTIVE, self.Status.PAST_DUE)


class Invoice(models.Model):
    """Facture générée par WeasyPrint, liée à un événement Stripe."""

    class InvoiceType(models.TextChoices):
        SUBSCRIPTION = 'subscription', 'Abonnement'
        SMS_PACK     = 'sms_pack',     'Pack SMS'

    pharmacy                   = models.ForeignKey(
                                     'core.Pharmacy',
                                     on_delete=models.PROTECT,
                                     related_name='invoices'
                                 )
    invoice_type               = models.CharField(max_length=20, choices=InvoiceType.choices)
    invoice_number             = models.CharField(max_length=50, unique=True)  # ex: LLO-2025-000001
    stripe_invoice_id          = models.CharField(max_length=255, unique=True, null=True, blank=True)
    stripe_payment_intent_id   = models.CharField(max_length=255, unique=True, null=True, blank=True)
    amount_ht                  = models.DecimalField(max_digits=10, decimal_places=2)
    tva_rate                   = models.DecimalField(max_digits=5, decimal_places=2, default=20.00)
    amount_ttc                 = models.DecimalField(max_digits=10, decimal_places=2)
    pdf_storage_key            = models.CharField(max_length=500, null=True, blank=True)  # clé Scaleway Object Storage
    issued_at                  = models.DateTimeField(auto_now_add=True)
    paid_at                    = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Facture'
        verbose_name_plural = 'Factures'
        ordering = ['-issued_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(invoice_type__in=['subscription', 'sms_pack']),
                name='billing_invoice_type_valid'
            ),
            models.CheckConstraint(
                condition=models.Q(amount_ht__gte=0),
                name='billing_invoice_amount_ht_positive'
            ),
        ]
        indexes = [
            models.Index(fields=['pharmacy', 'issued_at'], name='bill_inv_phcy_date_idx'),
            models.Index(fields=['invoice_type'], name='bill_inv_type_idx'),
        ]

    def __str__(self):
        return f"{self.invoice_number} — {self.pharmacy} ({self.amount_ttc}€ TTC)"

    @classmethod
    def generate_invoice_number(cls, invoice_type: str) -> str:
        """
        Génère un numéro séquentiel unique et thread-safe.
        Format : LLO-YYYY-XXXXXX (ex : LLO-2026-000001).
        SELECT FOR UPDATE pour éviter les doublons en concurrence.
        """
        from django.db import transaction
        from django.utils import timezone
        year = timezone.now().year

        with transaction.atomic():
            last = (
                cls.objects
                .filter(invoice_number__startswith=f'LLO-{year}-')
                .select_for_update()
                .order_by('-invoice_number')
                .first()
            )
            new_seq = int(last.invoice_number.split('-')[-1]) + 1 if last else 1
            return f'LLO-{year}-{new_seq:06d}'


class SmsCreditTransaction(models.Model):
    """Historique des mouvements de crédits SMS.

    Le solde reste porté par ``core.Pharmacy.sms_credits`` (source de vérité
    existante) ; ce modèle ne fait qu'enregistrer le journal des mouvements.
    """

    class Reason(models.TextChoices):
        PURCHASE = 'purchase', 'Achat de pack'
        SEND     = 'send',     'Envoi SMS'
        REFUND   = 'refund',   'Remboursement'
        CLOSURE  = 'closure',  'Clôture du compte'

    pharmacy   = models.ForeignKey(
                     'core.Pharmacy',
                     on_delete=models.PROTECT,
                     related_name='sms_transactions'
                 )
    delta      = models.IntegerField()   # positif = crédit, négatif = débit
    reason     = models.CharField(max_length=20, choices=Reason.choices)
    note       = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Transaction SMS'
        verbose_name_plural = 'Transactions SMS'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['pharmacy', 'created_at'], name='bill_sms_tx_phcy_date_idx'),
        ]

    def __str__(self):
        sign = '+' if self.delta > 0 else ''
        return f"{self.pharmacy} — {sign}{self.delta} SMS ({self.get_reason_display()})"


class PromoCode(models.Model):
    """
    Code promotionnel offrant N mois gratuits supplémentaires après le trial.
    Appliqué via extension du trial_period_days Stripe.
    """
    code         = models.CharField(max_length=50, unique=True)
    months_free  = models.PositiveSmallIntegerField(
                       help_text='Nombre de mois offerts après le mois d\'essai.'
                   )
    is_active    = models.BooleanField(default=True)
    max_uses     = models.PositiveIntegerField(
                       null=True, blank=True,
                       help_text='Laisser vide pour un usage illimité globalement.'
                   )
    current_uses = models.PositiveIntegerField(default=0)
    expires_at   = models.DateTimeField(
                       null=True, blank=True,
                       help_text='Laisser vide si pas de date d\'expiration.'
                   )
    note         = models.CharField(
                       max_length=255, blank=True,
                       help_text='Usage interne uniquement (ex: Offre groupement Giphar).'
                   )
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Code promo'
        verbose_name_plural = 'Codes promo'
        ordering            = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(months_free__gte=1),
                name='billing_promocode_months_free_min_1'
            ),
        ]
        indexes = [
            models.Index(fields=['code'],      name='billing_promocode_code_idx'),
            models.Index(fields=['is_active'], name='billing_promocode_active_idx'),
        ]

    def __str__(self):
        return f'{self.code} — {self.months_free} mois offerts'

    @property
    def trial_days_total(self) -> int:
        """Durée totale du trial en jours : 30 (essai) + N mois offerts."""
        return 30 + (self.months_free * 30)

    def is_valid(self) -> bool:
        """Vérifie que le code est utilisable (actif, non expiré, quota non atteint)."""
        from django.utils import timezone
        if not self.is_active:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        if self.max_uses is not None and self.current_uses >= self.max_uses:
            return False
        return True


class PromoRedemption(models.Model):
    """
    Enregistre l'utilisation d'un code promo par une pharmacie.
    Garantit l'usage unique par pharmacie via UniqueConstraint.
    """
    promo_code   = models.ForeignKey(
                       PromoCode,
                       on_delete=models.PROTECT,
                       related_name='redemptions'
                   )
    pharmacy     = models.ForeignKey(
                       'core.Pharmacy',
                       on_delete=models.PROTECT,
                       related_name='promo_redemptions'
                   )
    redeemed_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Utilisation code promo'
        verbose_name_plural = 'Utilisations codes promo'
        ordering            = ['-redeemed_at']
        constraints = [
            models.UniqueConstraint(
                fields=['promo_code', 'pharmacy'],
                name='billing_promoredemption_unique_per_pharmacy'
            ),
        ]
        indexes = [
            models.Index(
                fields=['pharmacy'],
                name='bill_promo_redempt_phcy_idx'
            ),
        ]

    def __str__(self):
        return f'{self.pharmacy} — {self.promo_code.code} — {self.redeemed_at:%d/%m/%Y}'
