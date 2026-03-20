import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from './auth.service';
import { ToastService } from '../services/toast.service';

export const qualityManagerGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const toastService = inject(ToastService);
  const router = inject(Router);

  if (authService.canManageQuality()) return true;

  toastService.warning('Vous n\'avez pas la permission de créer ou modifier des procédures.');
  router.navigate(['/quality']);
  return false;
};
