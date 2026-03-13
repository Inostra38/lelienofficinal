import { HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, switchMap, throwError } from 'rxjs';
import { AuthService } from './auth.service';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const authService = inject(AuthService);
  const router = inject(Router);
  const token = authService.getToken();

  const authReq = token
    ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
    : req;

  return next(authReq).pipe(
    catchError((err: HttpErrorResponse) => {
      // Sur 401, tenter un refresh silencieux (sauf si la requête échouée est elle-même un refresh ou un login)
      if (err.status === 401 && !req.url.includes('/token/')) {
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
      if (err.status === 401) {
        authService.logout(router.url);
      }
      return throwError(() => err);
    })
  );
};
