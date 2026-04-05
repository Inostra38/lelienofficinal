import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AdminAuthService } from './admin-auth.service';

/**
 * Protège les routes admin authentifiées.
 * Vérifie la présence du token EN MÉMOIRE uniquement (pas localStorage).
 * Si absent → redirige vers /admin/login.
 */
export const adminAuthGuard: CanActivateFn = () => {
  const adminAuthService = inject(AdminAuthService);
  const router = inject(Router);

  if (!adminAuthService.isAuthenticated()) {
    return router.createUrlTree(['/admin/login']);
  }

  return true;
};

/**
 * Empêche l'accès à /admin/login si l'admin est déjà authentifié.
 */
export const adminNoAuthGuard: CanActivateFn = () => {
  const adminAuthService = inject(AdminAuthService);
  const router = inject(Router);

  if (adminAuthService.isAuthenticated()) {
    return router.createUrlTree(['/admin']);
  }

  return true;
};
