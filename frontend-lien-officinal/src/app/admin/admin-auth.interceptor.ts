import { HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, switchMap, throwError } from 'rxjs';
import { AdminAuthService } from './admin-auth.service';

export const adminAuthInterceptor: HttpInterceptorFn = (req, next) => {
  // N'intercepte que les requêtes /api/admin/*
  if (!req.url.includes('/api/admin/')) {
    return next(req);
  }

  const adminAuthService = inject(AdminAuthService);
  const router = inject(Router);

  const isAuthEndpoint = req.url.includes('/api/admin/auth/');
  const token = adminAuthService.getAccessToken();

  const authReq = token
    ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
    : req;

  return next(authReq).pipe(
    catchError((err: HttpErrorResponse) => {
      // Guard middleware 403 → rediriger vers la page appropriée
      if (err.status === 403) {
        const body = typeof err.error === 'string' ? (() => { try { return JSON.parse(err.error); } catch { return {}; } })() : err.error;
        if (body?.code === 'password_change_required') {
          router.navigate(['/admin/change-password']);
          return throwError(() => err);
        }
        if (body?.code === 'totp_setup_required') {
          router.navigate(['/admin/totp-setup']);
          return throwError(() => err);
        }
      }

      // Sur 401 : tenter un refresh silencieux (sauf endpoints auth)
      if (err.status === 401 && !isAuthEndpoint) {
        return adminAuthService.refreshToken().pipe(
          switchMap(() => {
            const newToken = adminAuthService.getAccessToken();
            const retryReq = newToken
              ? req.clone({ setHeaders: { Authorization: `Bearer ${newToken}` } })
              : req;
            return next(retryReq);
          }),
          catchError(() => {
            router.navigate(['/admin/login']);
            return throwError(() => err);
          })
        );
      }

      // 401 sur endpoint auth → laisser remonter au composant
      return throwError(() => err);
    })
  );
};
