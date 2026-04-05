import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { BehaviorSubject, Observable, throwError } from 'rxjs';
import { tap, switchMap, catchError } from 'rxjs/operators';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class AdminAuthService {
  private http = inject(HttpClient);
  private router = inject(Router);
  private baseUrl = environment.apiUrl + '/api/admin/auth';

  // Access token uniquement en mémoire — jamais persisté
  private _accessToken: string | null = null;

  isAuthenticated$ = new BehaviorSubject<boolean>(false);

  // Guard contre les refreshes simultanés
  private _isRefreshing = false;

  login(email: string, password: string): Observable<{ step: string; session_token: string; totp_configured: boolean }> {
    return this.http.post<{ step: string; session_token: string; totp_configured: boolean }>(
      `${this.baseUrl}/login/`,
      { email, password }
    );
  }

  verifyTotp(sessionToken: string, totpCode: string): Observable<{ force_password_change: boolean; totp_configured: boolean }> {
    return this.http.post<{
      access_token: string;
      force_password_change: boolean;
      totp_configured: boolean;
    }>(
      `${this.baseUrl}/totp-verify/`,
      { session_token: sessionToken, totp_code: totpCode },
      { withCredentials: true }
    ).pipe(
      tap(response => {
        this._accessToken = response.access_token;
        this.isAuthenticated$.next(true);
      }),
      switchMap(response => new Observable<{ force_password_change: boolean; totp_configured: boolean }>(observer => {
        observer.next({
          force_password_change: response.force_password_change,
          totp_configured: response.totp_configured,
        });
        observer.complete();
      }))
    );
  }

  logout(): Observable<void> {
    return this.http.post<void>(
      `${this.baseUrl}/logout/`,
      {},
      { withCredentials: true }
    ).pipe(
      tap(() => this._clearSession()),
      catchError(err => {
        this._clearSession();
        return throwError(() => err);
      })
    );
  }

  refreshToken(): Observable<void> {
    if (this._isRefreshing) {
      return new Observable<void>(observer => {
        const sub = this.isAuthenticated$.subscribe(auth => {
          if (auth) { observer.next(); observer.complete(); sub.unsubscribe(); }
        });
      });
    }

    this._isRefreshing = true;
    return this.http.post<{ access_token: string }>(
      `${this.baseUrl}/refresh/`,
      {},
      { withCredentials: true }
    ).pipe(
      tap(response => {
        this._accessToken = response.access_token;
        this.isAuthenticated$.next(true);
        this._isRefreshing = false;
      }),
      switchMap(() => new Observable<void>(observer => {
        observer.next();
        observer.complete();
      })),
      catchError(err => {
        this._isRefreshing = false;
        this._clearSession();
        return throwError(() => err);
      })
    );
  }

  getAccessToken(): string | null {
    return this._accessToken;
  }

  isAuthenticated(): boolean {
    return this._accessToken !== null && !this._isTokenExpired(this._accessToken);
  }

  private _isTokenExpired(token: string): boolean {
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      return payload.exp * 1000 <= Date.now();
    } catch {
      return true;
    }
  }

  private _clearSession(): void {
    this._accessToken = null;
    this.isAuthenticated$.next(false);
    this.router.navigate(['/admin/login']);
  }
}
