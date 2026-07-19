import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { SubscriptionStateService } from '../../../core/services/subscription-state.service';

/**
 * Bannière d'information sur l'abonnement — jamais bloquante.
 *
 * Deux cas :
 *  - essai qui approche de sa fin (≤ 7 jours) → ton neutre, incitatif ;
 *  - accès payant refusé → ton d'alerte, mais l'application reste utilisable
 *    puisque le tableau de bord est gratuit. Le message le dit explicitement,
 *    pour ne pas laisser croire à une coupure totale.
 *
 * Calquée sur EmailBannerComponent (même emplacement, même grammaire visuelle).
 */
@Component({
  selector: 'app-subscription-banner',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    @if (visible() && !dismissed()) {
      <div class="border-b px-4 py-2 flex items-center justify-between text-sm"
           [class]="denied() ? 'bg-red-50 border-red-200' : 'bg-amber-50 border-amber-200'">
        <span [class]="denied() ? 'text-red-800' : 'text-amber-800'">{{ message() }}</span>
        <div class="flex items-center gap-3">
          <a routerLink="/account" [queryParams]="{ section: 'billing' }"
             class="text-green-700 font-medium hover:underline">
            {{ denied() ? 'Mettre à jour mon abonnement' : "S'abonner" }}
          </a>
          <!-- Un accès refusé n'est pas masquable : le titulaire doit agir. -->
          @if (!denied()) {
            <button (click)="dismissed.set(true)"
                    class="text-amber-500 hover:text-amber-700"
                    aria-label="Masquer">&#x2715;</button>
          }
        </div>
      </div>
    }
  `,
})
export class SubscriptionBannerComponent implements OnInit {
  private subscriptionState = inject(SubscriptionStateService);

  dismissed = signal(false);

  /** Seuil à partir duquel on prévient de la fin d'essai. */
  private static readonly WARN_DAYS = 7;

  readonly denied = computed(() => !this.subscriptionState.hasPaidAccess());

  readonly visible = computed(() => {
    if (!this.subscriptionState.loaded()) return false;
    if (this.denied()) return true;
    const daysLeft = this.subscriptionState.trialDaysLeft();
    return daysLeft !== null && daysLeft <= SubscriptionBannerComponent.WARN_DAYS;
  });

  readonly message = computed(() => {
    if (this.denied()) {
      const reason = this.subscriptionState.deniedReason();
      return DENIAL_MESSAGES[reason ?? 'canceled'];
    }
    const daysLeft = this.subscriptionState.trialDaysLeft() ?? 0;
    if (daysLeft <= 1) {
      return "Votre essai gratuit se termine aujourd'hui. Votre tableau de bord restera accessible.";
    }
    return `Votre essai gratuit se termine dans ${daysLeft} jours. Votre tableau de bord restera accessible.`;
  });

  ngOnInit(): void {
    this.subscriptionState.load().subscribe();
  }
}

const DENIAL_MESSAGES: Record<string, string> = {
  trial_expired:  "Votre essai est terminé — planning, qualité, tâches, messagerie et SMS sont suspendus. Votre tableau de bord reste gratuit.",
  payment_failed: "Votre dernier paiement a échoué. Mettez à jour vos informations bancaires sous 7 jours pour conserver vos modules.",
  suspended:      "Votre abonnement est suspendu pour impayé. Votre tableau de bord reste accessible.",
  canceled:       "Votre abonnement est résilié. Votre tableau de bord reste accessible.",
};
