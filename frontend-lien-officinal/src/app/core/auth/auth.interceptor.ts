import { HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, switchMap, throwError } from 'rxjs';
import { AuthService } from './auth.service';
import { ToastService } from '../services/toast.service';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const authService = inject(AuthService);
  const toastService = inject(ToastService);
  const router = inject(Router);
  const token = authService.getToken();

  const authReq = token
    ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
    : req;

  return next(authReq).pipe(
    catchError((err: HttpErrorResponse) => {
      // Sur 401, tenter un refresh silencieux (sauf refresh/login pharmacie ou tout endpoint admin)
      if (err.status === 401 && !req.url.includes('/token/') && !req.url.includes('/api/admin/')) {
        return authService.refreshAccessToken().pipe(
          switchMap(newToken => {
            const retryReq = req.clone({ setHeaders: { Authorization: `Bearer ${newToken}` } });
            return next(retryReq);
          }),
          catchError(() => {
            authService.logout(router.url);
            return throwError(() => err);
          })
        );
      }
      if (err.status === 401 && !req.url.includes('/api/admin/')) {
        authService.logout(router.url);
      }
      if (err.status === 403 && req.url.includes('/api/quality/')) {
        toastService.error('Action non autorisée : permission insuffisante.');
      }
      if (err.status === 429) {
        const detail = err.error?.detail ?? 'Trop de requêtes. Réessayez dans un moment.';
        toastService.error(detail);
      }
      return throwError(() => err);
    })
  );
};
