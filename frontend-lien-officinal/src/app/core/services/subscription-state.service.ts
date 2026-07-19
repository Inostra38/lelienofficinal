import { Injectable, computed, inject, signal } from '@angular/core';
import { Observable, catchError, map, of, tap } from 'rxjs';
import { BillingService, SubscriptionStatus } from './billing.service';

/**
 * État d'abonnement partagé — source unique pour le guard des modules payants
 * et la bannière d'information.
 *
 * Mis en cache : sans ça, chaque navigation vers un module payant déclencherait
 * un appel à /api/billing/status/. Le cache est invalidé après souscription ou
 * sur 402 (l'état serveur a changé).
 *
 * Rappel : le tableau de bord est GRATUIT. Ce service ne doit jamais servir à
 * en restreindre l'accès — il ne gouverne que les modules payants.
 */
@Injectable({ providedIn: 'root' })
export class SubscriptionStateService {
  private billingService = inject(BillingService);

  private readonly _subscription = signal<SubscriptionStatus | null>(null);
  private readonly _loaded = signal(false);

  readonly subscription = this._subscription.asReadonly();
  readonly loaded = this._loaded.asReadonly();

  /**
   * Accès aux modules payants. Optimiste tant que l'état n'est pas chargé :
   * on ne bloque pas l'utilisateur sur une information qu'on n'a pas encore.
   */
  readonly hasPaidAccess = computed(() => {
    if (!this._loaded()) return true;
    return this._subscription()?.is_access_allowed ?? false;
  });

  readonly deniedReason = computed(() => this._subscription()?.access_denied_reason ?? null);

  /** Jours restants d'essai, ou null hors période d'essai. */
  readonly trialDaysLeft = computed(() => {
    const sub = this._subscription();
    if (!sub || sub.status !== 'trialing' || !sub.trial_ends_at) return null;
    const ms = new Date(sub.trial_ends_at).getTime() - Date.now();
    return ms <= 0 ? 0 : Math.ceil(ms / 86_400_000);
  });

  /** Charge l'état une seule fois, sauf `force`. */
  load(force = false): Observable<SubscriptionStatus | null> {
    if (this._loaded() && !force) return of(this._subscription());

    return this.billingService.getStatus().pipe(
      tap(response => {
        this._subscription.set(response.subscription);
        this._loaded.set(true);
      }),
      // Les appelants n'ont besoin que de l'abonnement, pas du solde SMS.
      map(response => response.subscription),
      catchError(() => {
        // Un statut injoignable ne doit pas verrouiller les modules : on reste
        // optimiste (hasPaidAccess renvoie true tant que _loaded est faux) et
        // c'est le 402 du backend qui fera autorité.
        return of(this._subscription());
      }),
    );
  }

  /** À appeler après une souscription ou un 402 : l'état serveur a changé. */
  invalidate(): void {
    this._loaded.set(false);
  }
}
