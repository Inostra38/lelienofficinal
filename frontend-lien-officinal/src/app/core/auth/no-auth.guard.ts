import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from './auth.service';

/**
 * Empêche l'accès aux routes publiques (login) si l'utilisateur
 * est déjà authentifié. Redirige vers /dashboard dans ce cas.
 */
export const noAuthGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (authService.isAuthenticated()) {
    return router.createUrlTree(['/dashboard']);
  }

  return true;
};
