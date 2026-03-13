import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from './auth.service';

/**
 * Protège la route /onboarding :
 * - Non authentifié → /login
 * - Onboarding déjà complété → /dashboard
 * - Authentifié + onboarding en cours → accès autorisé
 */
export const onboardingGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (!authService.isAuthenticated()) {
    return router.createUrlTree(['/login']);
  }

  if (authService.isOnboardingCompleted()) {
    return router.createUrlTree(['/dashboard']);
  }

  return true;
};
