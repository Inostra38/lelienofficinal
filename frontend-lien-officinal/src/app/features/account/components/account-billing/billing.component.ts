import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { loadStripe, Stripe, StripeElements } from '@stripe/stripe-js';
import { environment } from '../../../../../environments/environment';
import { BillingService, BillingStatusResponse, Invoice } from '../../../../core/services/billing.service';

@Component({
  selector: 'app-account-billing',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './billing.component.html',
})
export class AccountBillingComponent implements OnInit {
  private billingService = inject(BillingService);

  // State
  status = signal<BillingStatusResponse | null>(null);
  invoices = signal<Invoice[]>([]);
  loading = signal(true);
  sepaLoading = signal(false);
  sepaReady = signal(false);        // true une fois le champ IBAN monté
  ownerName = signal('');
  ownerEmail = signal('');
  smsLoading = signal<'S' | 'M' | 'L' | null>(null);
  successMessage = signal<string | null>(null);
  errorMessage = signal<string | null>(null);

  // Code promo
  promoCode = signal('');
  promoValidation = signal<{
    valid: boolean;
    months_free?: number;
    message?: string;
    error?: string;
  } | null>(null);
  promoLoading = signal(false);

  // Stripe
  private stripe: Stripe | null = null;
  private elements: StripeElements | null = null;

  // Achat pack SMS (paiement carte)
  selectedPack = signal<'S' | 'M' | 'L' | null>(null);
  paymentProcessing = signal(false);
  private smsClientSecret: string | null = null;
  private cardElement: any = null;

  readonly smsPacks = [
    { key: 'S' as const, label: '100 SMS', price: '9€' },
    { key: 'M' as const, label: '250 SMS', price: '22€' },
    { key: 'L' as const, label: '500 SMS', price: '39€' },
  ];

  ngOnInit() {
    // Le chargement des données ne doit PAS dépendre de Stripe.js : si loadStripe
    // échoue (clé placeholder, CSP bloquant js.stripe.com, hors-ligne), l'UI doit
    // quand même s'afficher. On charge donc Stripe en parallèle, sans bloquer.
    this.loadData();
    void this.initStripe();
  }

  private async initStripe(): Promise<void> {
    try {
      this.stripe = await loadStripe(environment.stripePk);
    } catch {
      this.stripe = null;  // les fonctions SEPA se dégradent proprement
    }
  }

  private loadData() {
    this.loading.set(true);
    this.billingService.getStatus().subscribe({
      next: (data) => {
        this.status.set(data);
        this.loading.set(false);
      },
      error: () => {
        this.errorMessage.set('Impossible de charger les informations de facturation. Réessayez plus tard.');
        this.loading.set(false);
      },
    });

    this.billingService.getInvoices().subscribe({
      next: (invoices) => this.invoices.set(invoices),
    });
  }

  // ------------------------------------------------------------------ //
  // SEPA Setup                                                           //
  // ------------------------------------------------------------------ //

  setupSepa() {
    this.sepaLoading.set(true);
    this.errorMessage.set(null);

    this.billingService.setupSubscription().subscribe({
      next: async ({ client_secret }) => {
        if (!this.stripe) return;

        this.elements = this.stripe.elements({ clientSecret: client_secret });

        const sepaElement = this.elements.create('iban', {
          supportedCountries: ['SEPA'],
          placeholderCountry: 'FR',
          style: {
            base: {
              fontSize: '16px',
              color: '#1f2937',
              '::placeholder': { color: '#9ca3af' },
            },
          },
        });

        sepaElement.mount('#sepa-element');
        this.sepaReady.set(true);
        this.sepaLoading.set(false);
      },
      error: () => {
        this.errorMessage.set('Erreur lors de l\'initialisation du paiement.');
        this.sepaLoading.set(false);
      },
    });
  }

  async confirmSepa(ownerName: string, ownerEmail: string) {
    if (!this.stripe || !this.elements) return;
    this.sepaLoading.set(true);

    const sepaElement = this.elements.getElement('iban');
    if (!sepaElement) return;

    const { setupIntent, error } = await this.stripe.confirmSepaDebitSetup(
      (this.elements as any)._commonOptions.clientSecret,
      {
        payment_method: {
          sepa_debit: sepaElement,
          billing_details: { name: ownerName, email: ownerEmail },
        },
      }
    );

    if (error) {
      this.errorMessage.set(error.message ?? 'Erreur SEPA');
      this.sepaLoading.set(false);
      return;
    }

    this.billingService.confirmSubscription(
      setupIntent!.payment_method as string,
      this.promoCode() || undefined,
    ).subscribe({
      next: () => {
        this.successMessage.set('Abonnement activé avec succès !');
        this.sepaReady.set(false);
        this.loadData();
        this.sepaLoading.set(false);
      },
      error: () => {
        this.errorMessage.set('Erreur lors de l\'activation de l\'abonnement.');
        this.sepaLoading.set(false);
      },
    });
  }

  // ------------------------------------------------------------------ //
  // Code promo                                                           //
  // ------------------------------------------------------------------ //

  validatePromo() {
    const code = this.promoCode().trim();
    if (!code) return;

    this.promoLoading.set(true);
    this.promoValidation.set(null);

    this.billingService.validatePromoCode(code).subscribe({
      next: (result) => {
        this.promoValidation.set(result);
        this.promoLoading.set(false);
      },
      error: (err) => {
        this.promoValidation.set({
          valid: false,
          error: err.error?.error ?? 'Code invalide.',
        });
        this.promoLoading.set(false);
      },
    });
  }

  // ------------------------------------------------------------------ //
  // SMS Pack                                                             //
  // ------------------------------------------------------------------ //

  buySmsPack(pack: 'S' | 'M' | 'L') {
    this.errorMessage.set(null);
    this.successMessage.set(null);
    this.smsLoading.set(pack);

    // 1) Crée le PaymentIntent côté backend, puis 2) révèle le formulaire carte.
    this.billingService.createSmsPackIntent(pack).subscribe({
      next: ({ client_secret }) => {
        this.smsClientSecret = client_secret;
        this.selectedPack.set(pack);
        this.smsLoading.set(null);
        // Monte le Card Element une fois le <div id="sms-card-element"> rendu.
        setTimeout(() => this.mountCardElement(), 0);
      },
      error: () => {
        this.errorMessage.set('Erreur lors de la création du paiement.');
        this.smsLoading.set(null);
      },
    });
  }

  private mountCardElement() {
    if (!this.stripe) {
      this.errorMessage.set('Le module de paiement n\'a pas pu se charger. Réessayez.');
      this.cancelSmsPayment();
      return;
    }
    if (this.cardElement) {
      this.cardElement.unmount();
      this.cardElement = null;
    }
    const elements = this.stripe.elements();
    this.cardElement = elements.create('card', {
      style: {
        base: {
          fontSize: '16px',
          color: '#1f2937',
          '::placeholder': { color: '#9ca3af' },
        },
      },
    });
    this.cardElement.mount('#sms-card-element');
  }

  async paySmsPack() {
    if (!this.stripe || !this.cardElement || !this.smsClientSecret) return;
    this.paymentProcessing.set(true);
    this.errorMessage.set(null);

    const { error, paymentIntent } = await this.stripe.confirmCardPayment(
      this.smsClientSecret,
      { payment_method: { card: this.cardElement } },
    );

    if (error) {
      this.errorMessage.set(error.message ?? 'Le paiement a échoué.');
      this.paymentProcessing.set(false);
      return;
    }

    if (paymentIntent?.status === 'succeeded') {
      this.successMessage.set('Paiement réussi ! Vos crédits SMS seront ajoutés sur votre solde dans quelques instants.');
      this.cancelSmsPayment();
      this.loadData();
    }
    this.paymentProcessing.set(false);
  }

  cancelSmsPayment() {
    if (this.cardElement) {
      this.cardElement.unmount();
      this.cardElement = null;
    }
    this.smsClientSecret = null;
    this.selectedPack.set(null);
    this.paymentProcessing.set(false);
  }

  selectedPackLabel(): string {
    return this.smsPacks.find(p => p.key === this.selectedPack())?.label ?? '';
  }

  selectedPackPrice(): string {
    return this.smsPacks.find(p => p.key === this.selectedPack())?.price ?? '';
  }

  // ------------------------------------------------------------------ //
  // Helpers                                                              //
  // ------------------------------------------------------------------ //

  downloadInvoice(inv: Invoice) {
    this.errorMessage.set(null);
    this.billingService.downloadInvoice(inv.id).subscribe({
      next: ({ download_url }) => window.open(download_url, '_blank'),
      error: () => this.errorMessage.set('Téléchargement de la facture impossible.'),
    });
  }

  statusLabel(status: string): string {
    const labels: Record<string, string> = {
      trialing:  'Essai gratuit',
      active:    'Actif',
      past_due:  'Paiement en retard',
      suspended: 'Suspendu',
      canceled:  'Résilié',
    };
    return labels[status] ?? status;
  }

  statusBadgeClass(status: string): string {
    const base = 'px-2 py-1 rounded-full text-xs font-medium';
    const colors: Record<string, string> = {
      trialing:  'bg-green-50 text-green-700',
      active:    'bg-green-100 text-green-800',
      past_due:  'bg-amber-100 text-amber-700',
      suspended: 'bg-red-100 text-red-700',
      canceled:  'bg-gray-100 text-gray-500',
    };
    return `${base} ${colors[status] ?? 'bg-gray-100 text-gray-500'}`;
  }
}
