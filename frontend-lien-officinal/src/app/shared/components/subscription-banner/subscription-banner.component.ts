import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { SubscriptionStateService } from '../../../core/services/subscription-state.service';

type BannerMode = 'denied' | 'grace' | 'trial';

/**
 * Bannière d'information sur l'abonnement — jamais bloquante.
 *
 * Trois modes, du plus grave au plus léger :
 *  - `denied`  : accès payant coupé (essai expiré, impayé dépassé, suspendu,
 *                résilié). Ton d'alerte (rouge). Le tableau de bord reste gratuit.
 *  - `grace`   : impayé encore dans les 7 jours de grâce — l'accès tient, mais on
 *                prévient AVANT la coupure, avec un compte à rebours. Ton ambre.
 *  - `trial`   : essai qui approche de sa fin (≤ 7 jours). Ton ambre.
 *
 * Fermeture persistante (localStorage), mémorisée PAR MODE/MOTIF : fermer
 * « essai expiré » ne masque pas un futur « abonnement suspendu ». Le verrou des
 * onglets et la page facturation restent visibles — fermer n'occulte rien.
 */
@Component({
  selector: 'app-subscription-banner',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    @if (visible()) {
      <div class="border-b px-4 py-2 flex items-center justify-between text-sm"
           [class]="mode() === 'denied' ? 'bg-red-50 border-red-200' : 'bg-amber-50 border-amber-200'">
        <span [class]="mode() === 'denied' ? 'text-red-800' : 'text-amber-800'">{{ message() }}</span>
        <div class="flex items-center gap-3">
          <a routerLink="/account" [queryParams]="{ section: 'billing' }"
             class="text-green-700 font-medium hover:underline">
            {{ ctaLabel() }}
          </a>
          <button (click)="dismiss()"
                  [class]="mode() === 'denied' ? 'text-red-400 hover:text-red-700' : 'text-amber-500 hover:text-amber-700'"
                  aria-label="Masquer">&#x2715;</button>
        </div>
      </div>
    }
  `,
})
export class SubscriptionBannerComponent implements OnInit {
  private subscriptionState = inject(SubscriptionStateService);

  /** Incrémenté à chaque fermeture pour re-évaluer `dismissed` (localStorage n'est pas réactif). */
  private readonly dismissTick = signal(0);

  /** Seuil à partir duquel on prévient de la fin d'essai. */
  private static readonly WARN_DAYS = 7;

  /** Situation courante, ou null si aucune bannière n'a lieu d'être. */
  readonly mode = computed<BannerMode | null>(() => {
    if (!this.subscriptionState.loaded()) return null;
    if (!this.subscriptionState.hasPaidAccess()) return 'denied';
    // Accès ouvert à partir d'ici.
    if (this.subscriptionState.subscription()?.status === 'past_due') return 'grace';
    const daysLeft = this.subscriptionState.trialDaysLeft();
    if (daysLeft !== null && daysLeft <= SubscriptionBannerComponent.WARN_DAYS) return 'trial';
    return null;
  });

  /** Clé de fermeture propre à la situation courante. */
  private readonly dismissKey = computed(() => {
    switch (this.mode()) {
      case 'denied': return `llo.subBanner.denied.${this.subscriptionState.deniedReason() ?? 'unknown'}`;
      case 'grace':  return 'llo.subBanner.pastDueGrace';
      case 'trial':  return 'llo.subBanner.trialWarning';
      default:       return '';
    }
  });

  private readonly dismissed = computed(() => {
    this.dismissTick();
    return this.readDismissed(this.dismissKey());
  });

  readonly visible = computed(() => this.mode() !== null && !this.dismissed());

  readonly message = computed(() => {
    switch (this.mode()) {
      case 'denied':
        return DENIAL_MESSAGES[this.subscriptionState.deniedReason() ?? 'canceled'];
      case 'grace': {
        const days = this.subscriptionState.subscription()?.grace_days_left ?? 0;
        const delai = days <= 1 ? "sous 1 jour" : `sous ${days} jours`;
        return `Votre dernier paiement a échoué. Mettez à jour votre RIB ${delai} pour conserver vos modules.`;
      }
      case 'trial': {
        const daysLeft = this.subscriptionState.trialDaysLeft() ?? 0;
        if (daysLeft <= 1) {
          return "Votre essai gratuit se termine aujourd'hui. Votre tableau de bord restera accessible.";
        }
        return `Votre essai gratuit se termine dans ${daysLeft} jours. Votre tableau de bord restera accessible.`;
      }
      default:
        return '';
    }
  });

  readonly ctaLabel = computed(() => {
    switch (this.mode()) {
      case 'denied': return 'Mettre à jour mon abonnement';
      case 'grace':  return 'Mettre à jour mon RIB';
      default:       return "S'abonner";
    }
  });

  dismiss(): void {
    this.writeDismissed(this.dismissKey());
    this.dismissTick.update(n => n + 1);
  }

  ngOnInit(): void {
    this.subscriptionState.load().subscribe();
  }

  // localStorage peut lever (mode privé, quota, SSR) — la fermeture est un
  // confort, jamais une garantie : on échoue en silence sans casser l'affichage.
  private readDismissed(key: string): boolean {
    if (!key) return false;
    try {
      return localStorage.getItem(key) === '1';
    } catch {
      return false;
    }
  }

  private writeDismissed(key: string): void {
    if (!key) return;
    try {
      localStorage.setItem(key, '1');
    } catch { /* ignore */ }
  }
}

// Accès COUPÉ : « retrouver » (les modules sont déjà perdus), sans délai — le
// « sous X jours pour conserver » est le langage du mode `grace`, ci-dessus.
const DENIAL_MESSAGES: Record<string, string> = {
  trial_expired:  "Votre essai est terminé — planning, qualité, tâches, messagerie et SMS sont suspendus. Votre tableau de bord reste gratuit.",
  payment_failed: "Votre dernier paiement a échoué. Mettez à jour vos informations bancaires pour retrouver vos modules.",
  suspended:      "Votre abonnement est suspendu pour impayé. Votre tableau de bord reste accessible.",
  canceled:       "Votre abonnement est résilié. Votre tableau de bord reste accessible.",
};
