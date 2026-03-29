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
  const token = adminAuthService.getAccessToken();

  const authReq = token
    ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
    : req;

  return next(authReq).pipe(
    catchError((err: HttpErrorResponse) => {
      // Sur 401 : tenter un refresh silencieux (sauf si c'est déjà un appel auth)
      if (err.status === 401 && !req.url.includes('/api/admin/auth/')) {
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

      if (err.status === 401) {
        router.navigate(['/admin/login']);
      }

      return throwError(() => err);
    })
  );
};
