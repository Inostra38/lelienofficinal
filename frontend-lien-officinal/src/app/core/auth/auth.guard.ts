import { inject } from '@angular/core';
import { Router, CanActivateFn } from '@angular/router';
import { AuthService } from './auth.service';
import { map, catchError } from 'rxjs/operators';
import { of } from 'rxjs';

export const authGuard: CanActivateFn = (route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  // Token en mémoire et non expiré → accès immédiat
  if (authService.isAuthenticated()) {
    if (!authService.isOnboardingCompleted() && !state.url.startsWith('/onboarding')) {
      router.navigate(['/onboarding']);
      return false;
    }
    return true;
  }

  // Pas de token en mémoire (reload) → tenter un refresh via cookie HttpOnly
  return authService.refreshAccessToken().pipe(
    map(() => {
      if (!authService.isOnboardingCompleted() && !state.url.startsWith('/onboarding')) {
        router.navigate(['/onboarding']);
        return false;
      }
      return true;
    }),
    catchError(() => {
      router.navigate(['/login'], { queryParams: { returnUrl: state.url } });
      return of(false);
    })
  );
};
