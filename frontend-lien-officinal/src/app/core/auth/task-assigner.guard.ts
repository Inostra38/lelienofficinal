import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from './auth.service';
import { ToastService } from '../services/toast.service';

export const taskAssignerGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const toastService = inject(ToastService);
  const router = inject(Router);

  if (authService.canAssignTask()) return true;

  toastService.warning('Vous n\'avez pas la permission d\'assigner des tâches.');
  router.navigate(['/dashboard']);
  return false;
};
