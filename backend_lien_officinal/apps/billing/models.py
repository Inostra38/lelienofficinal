from datetime import timedelta

from django.db import models
from django.utils import timezone


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
    past_due_since         = models.DateTimeField(
                                 null=True, blank=True,
                                 help_text="Entrée en impayé — origine du délai de grâce de 7 jours."
                             )
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

    #: Durée de l'essai, ouvrant toute la plateforme. Aligné sur le
    #: ``trial_days`` transmis à Stripe lors de la souscription.
    TRIAL_DAYS = 30

    #: Délai de grâce accordé après un échec de paiement, avant coupure des
    #: modules payants. Le titulaire est invité à mettre à jour sa carte.
    PAST_DUE_GRACE = timedelta(days=7)

    @property
    def is_access_allowed(self):
        """Accès aux modules PAYANTS (planning, qualité, tâches, messagerie, SMS).

        Le tableau de bord est gratuit et n'est JAMAIS soumis à cette règle :
        voir apps.billing.permissions.HasPaidAccess.

        Calculé à la volée depuis les dates, et non depuis le seul statut :
        un essai expiré ou un impayé dépassé perd l'accès même si aucune tâche
        planifiée n'est passée basculer le statut. L'accès ne dépend donc ni de
        Celery ni de Redis.
        """
        now = timezone.now()

        if self.status == self.Status.ACTIVE:
            return True

        if self.status == self.Status.TRIALING:
            # Sans date de fin, l'essai n'a pas encore démarré côté Stripe :
            # on l'accorde plutôt que de couper un compte fraîchement créé.
            return self.trial_ends_at is None or self.trial_ends_at > now

        if self.status == self.Status.PAST_DUE:
            # Délai de grâce de 7 jours. Sans horodatage (impayé antérieur à
            # l'ajout du champ), on accorde le bénéfice du doute.
            return (
                self.past_due_since is None
                or now - self.past_due_since < self.PAST_DUE_GRACE
            )

        # SUSPENDED, CANCELED
        return False

    @property
    def access_denied_reason(self):
        """Motif de refus, destiné au frontend. None si l'accès est ouvert."""
        if self.is_access_allowed:
            return None
        if self.status == self.Status.TRIALING:
            return 'trial_expired'
        if self.status == self.Status.PAST_DUE:
            return 'payment_failed'
        if self.status == self.Status.SUSPENDED:
            return 'suspended'
        return 'canceled'


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
    def _next_invoice_number(cls, year: int) -> str:
        """Calcule le prochain numéro. DOIT être appelé dans une transaction
        (le SELECT FOR UPDATE n'a de sens qu'à l'intérieur d'une transaction)."""
        last = (
            cls.objects
            .filter(invoice_number__startswith=f'LLO-{year}-')
            .select_for_update()
            .order_by('-invoice_number')
            .first()
        )
        new_seq = int(last.invoice_number.split('-')[-1]) + 1 if last else 1
        return f'LLO-{year}-{new_seq:06d}'

    @classmethod
    def generate_invoice_number(cls, invoice_type: str) -> str:
        """Numéro seul (usage tests / compat). Pour CRÉER une facture, utiliser
        create_with_sequential_number : le numéro seul relâche le verrou avant
        l'insert de l'appelant (C19), donc deux créations concurrentes tirent le
        même numéro."""
        from django.db import transaction
        from django.utils import timezone
        with transaction.atomic():
            return cls._next_invoice_number(timezone.now().year)

    @classmethod
    def create_with_sequential_number(cls, *, invoice_type, **fields):
        """C19 : réserve le numéro ET insère la facture dans UNE SEULE
        transaction, pour que le verrou SELECT FOR UPDATE tienne jusqu'à
        l'insertion. Retry sur la contrainte unique (course table-vide, où il
        n'y a pas de ligne à verrouiller)."""
        from django.db import IntegrityError, transaction
        from django.utils import timezone
        year = timezone.now().year
        for attempt in range(5):
            try:
                with transaction.atomic():
                    number = cls._next_invoice_number(year)
                    return cls.objects.create(
                        invoice_number=number, invoice_type=invoice_type, **fields
                    )
            except IntegrityError:
                if attempt == 4:
                    raise


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
    # Idempotence des crédits d'achat : un PaymentIntent ne peut être crédité
    # qu'une seule fois (contrainte unique partielle ci-dessous).
    stripe_payment_intent_id = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Transaction SMS'
        verbose_name_plural = 'Transactions SMS'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['stripe_payment_intent_id'],
                condition=models.Q(stripe_payment_intent_id__isnull=False),
                name='bill_sms_tx_pi_unique',
            ),
        ]
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
