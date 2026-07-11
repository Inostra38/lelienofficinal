import { HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, switchMap, throwError } from 'rxjs';
import { AuthService } from './auth.service';
import { ToastService } from '../services/toast.service';
import { environment } from '../../../environments/environment';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const authService = inject(AuthService);
  const toastService = inject(ToastService);
  const router = inject(Router);
  const token = authService.getToken();

  // C04/C05 : n'attacher le jeton QU'AUX requêtes vers notre API. Sinon une URL
  // externe passée à HttpClient (ex. item.final_url d'un lien partenaire) recevait
  // le JWT pharmacie → exfiltration. On accepte les URL relatives (même origine,
  // cas de la prod où le frontend est servi par Django) et, si apiUrl est défini
  // (dev), l'API absolue. Le garde !!environment.apiUrl évite le piège
  // startsWith('') — toujours vrai — quand apiUrl est vide en prod.
  const isOurApi =
    req.url.startsWith('/') ||
    (!!environment.apiUrl && req.url.startsWith(environment.apiUrl));
  const authReq = (token && isOurApi)
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
      if (err.status === 401 && !req.url.includes('/api/admin/') && !req.url.includes('/token/')) {
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
