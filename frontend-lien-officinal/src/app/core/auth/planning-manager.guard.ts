import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from './auth.service';
import { ToastService } from '../services/toast.service';

export const planningManagerGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const toastService = inject(ToastService);
  const router = inject(Router);

  if (authService.canManagePlanning()) return true;

  toastService.warning('Vous n\'avez pas la permission de gérer le planning.');
  router.navigate(['/dashboard']);
  return false;
};
