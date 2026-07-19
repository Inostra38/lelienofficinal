import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { map } from 'rxjs';
import { SubscriptionStateService } from '../services/subscription-state.service';
import { ToastService } from '../services/toast.service';

/**
 * Protège les routes des modules PAYANTS (planning, qualité, tâches,
 * messagerie, SMS).
 *
 * À ne JAMAIS poser sur /dashboard ni sur /account : le tableau de bord est
 * gratuit, et l'utilisateur doit pouvoir atteindre la facturation pour
 * régulariser justement quand son accès est refusé.
 *
 * Ce guard n'est qu'un confort d'affichage — il évite d'ouvrir un écran qui se
 * remplirait d'erreurs. L'autorité reste le backend, qui renvoie 402.
 */
export const paidAccessGuard: CanActivateFn = () => {
  const subscriptionState = inject(SubscriptionStateService);
  const toastService = inject(ToastService);
  const router = inject(Router);

  return subscriptionState.load().pipe(
    map(() => {
      if (subscriptionState.hasPaidAccess()) return true;

      toastService.warning(DENIAL_MESSAGES[subscriptionState.deniedReason() ?? 'canceled']);
      // Vers la facturation, pas vers /dashboard : l'utilisateur vient de
      // cliquer sur un module, il faut lui montrer comment le débloquer.
      return router.createUrlTree(['/account'], { queryParams: { section: 'billing' } });
    }),
  );
};

const DENIAL_MESSAGES: Record<string, string> = {
  trial_expired:  "Votre essai gratuit est terminé. Votre tableau de bord reste accessible.",
  payment_failed: "Votre dernier paiement a échoué. Mettez à jour vos informations bancaires.",
  suspended:      "Votre abonnement est suspendu. Régularisez pour retrouver ce module.",
  canceled:       "Votre abonnement est résilié. Réabonnez-vous pour retrouver ce module.",
};
