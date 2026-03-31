import { environment } from '../../../environments/environment';
import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { BehaviorSubject, Observable, throwError, of } from 'rxjs';
import { tap, switchMap, map, filter, take, catchError } from 'rxjs/operators';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private http = inject(HttpClient);
  private router = inject(Router);
  private baseUrl = environment.apiUrl + '/api';

  private onboardingKey = 'onboarding_completed';
  private emailVerifiedKey = 'email_verified';
  private collaboratorKey = 'active_collaborator_id';

  // ── Tokens en mémoire (non persistants — récupérés via cookie refresh au reload) ──
  private _accessToken: string | null = null;
  private _pharmacyAccessToken: string | null = null;  // sauvegardé pendant session collab

  private collaboratorSubject = new BehaviorSubject<number | null>(null);
  readonly collaborator$ = this.collaboratorSubject.asObservable();

  // Guard contre les refreshes simultanés
  private isRefreshing = false;
  private refreshSubject = new BehaviorSubject<string | null>(null);

  login(credentials: any) {
    return this.http.post<any>(`${this.baseUrl}/token/`, credentials, { withCredentials: true }).pipe(
      tap(response => {
        this._accessToken = response.access;
        this.collaboratorSubject.next(null);
      }),
      switchMap(() => {
        return this.http.get<any>(`${this.baseUrl}/pharmacy/me/`);
      }),
      tap(profile => {
        localStorage.setItem(this.onboardingKey, profile.onboarding_completed ? 'true' : 'false');
        localStorage.setItem(this.emailVerifiedKey, profile.email_verified ? 'true' : 'false');
      })
    );
  }

  register(data: { email: string; password: string; password_confirm: string }) {
    return this.http.post<any>(`${this.baseUrl}/auth/register/`, data, { withCredentials: true }).pipe(
      tap(response => {
        this._accessToken = response.access;
        localStorage.setItem(this.onboardingKey, 'false');
        localStorage.setItem(this.emailVerifiedKey, 'false');
      })
    );
  }

  logout(returnUrl?: string) {
    // Notifier le backend pour blacklister le refresh token et effacer le cookie
    this.http.post(`${this.baseUrl}/auth/logout/`, {}, { withCredentials: true }).subscribe();
    this._accessToken = null;
    this._pharmacyAccessToken = null;
    localStorage.removeItem(this.onboardingKey);
    localStorage.removeItem(this.emailVerifiedKey);
    localStorage.removeItem(this.collaboratorKey);
    this.collaboratorSubject.next(null);
    this.router.navigate(['/login'], returnUrl ? { queryParams: { returnUrl } } : {});
  }

  // ── Session collaborateur ─────────────────────────────────────────────────

  collaboratorLogin(collaboratorId: number, pin: string) {
    return this.http.post<any>(`${this.baseUrl}/team/login/`, {
      collaborator_id: collaboratorId,
      pin_code: pin
    }).pipe(
      tap(response => {
        if (this.getAuthType() !== 'collaborator') {
          this._pharmacyAccessToken = this._accessToken;
        }
        this._accessToken = response.access;
        this.collaboratorSubject.next(collaboratorId);
      })
    );
  }

  clearCurrentCollaborator(): void {
    this._accessToken = this._pharmacyAccessToken;
    this._pharmacyAccessToken = null;
    localStorage.removeItem(this.collaboratorKey);
    this.collaboratorSubject.next(null);
    // Notifier le backend pour restaurer session_info → pharmacy_account
    this.http.post(`${this.baseUrl}/auth/collab-logout/`, {}, { withCredentials: true }).subscribe();
  }

  /** @deprecated Utiliser collaboratorLogin() à la place */
  setCurrentCollaboratorId(id: number): void {
    localStorage.setItem(this.collaboratorKey, String(id));
    this.collaboratorSubject.next(id);
  }

  getCurrentCollaboratorId(): number | null {
    const fromToken = this._readCollaboratorIdFromToken();
    if (fromToken !== null) return fromToken;
    // Fallback : session_info cookie (après reload)
    return this._getSessionInfo()?.['collaborator_id'] ?? null;
  }

  // ── Refresh token ─────────────────────────────────────────────────────────

  refreshAccessToken(): Observable<string> {
    if (this.isRefreshing) {
      return this.refreshSubject.pipe(
        filter((token): token is string => token !== null),
        take(1)
      );
    }

    this.isRefreshing = true;
    this.refreshSubject.next(null);

    // Aucun body : le refresh token est dans le cookie HttpOnly
    return this.http.post<any>(
      `${this.baseUrl}/token/refresh/`,
      {},
      { withCredentials: true }
    ).pipe(
      tap(response => {
        this._accessToken = response.access;
        this.isRefreshing = false;
        this.refreshSubject.next(response.access);
      }),
      map(response => response.access as string),
      catchError(err => {
        this.isRefreshing = false;
        this.refreshSubject.next(null);
        return throwError(() => err);
      })
    );
  }

  getRefreshToken(): string | null {
    return null;  // Stocké en cookie HttpOnly — non accessible par JS
  }

  // ── Auth state ────────────────────────────────────────────────────────────

  canManageQuality(): boolean   { return this._getClaim('can_manage_quality'); }
  canManagePlanning(): boolean  { return this._getClaim('can_manage_planning'); }
  canManageAccount(): boolean   { return this._getClaim('can_manage_account'); }
  canManageTeam(): boolean      { return this._getClaim('can_manage_team'); }
  canAssignTask(): boolean      { return this._getClaim('can_assign_task'); }

  private _getClaim(claim: string): boolean {
    if (this._accessToken) {
      try {
        const payload = JSON.parse(atob(this._accessToken.split('.')[1]));
        return payload[claim] === true;
      } catch {}
    }
    return this._getSessionInfo()?.[claim] === true;
  }

  getAuthType(): 'pharmacy_account' | 'collaborator' | null {
    if (this._accessToken) {
      try {
        const payload = JSON.parse(atob(this._accessToken.split('.')[1]));
        return payload.auth_type ?? 'pharmacy_account';
      } catch {}
    }
    return this._getSessionInfo()?.['auth_type'] ?? null;
  }

  isAuthenticated(): boolean {
    if (this._accessToken) {
      try {
        const payload = JSON.parse(atob(this._accessToken.split('.')[1]));
        return payload.exp * 1000 > Date.now();
      } catch { return false; }
    }
    // Fallback : session_info cookie (page reload — le refresh se déclenchera sur le premier appel API)
    return !!this._getSessionInfo()?.['auth_type'];
  }

  isOnboardingCompleted(): boolean {
    return localStorage.getItem(this.onboardingKey) === 'true';
  }

  setOnboardingCompleted() {
    localStorage.setItem(this.onboardingKey, 'true');
  }

  isEmailVerified(): boolean {
    return localStorage.getItem(this.emailVerifiedKey) === 'true';
  }

  setEmailVerified() {
    localStorage.setItem(this.emailVerifiedKey, 'true');
  }

  verifyEmail(token: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/auth/verify-email/`, { token });
  }

  resendVerification(): Observable<any> {
    return this.http.post(`${this.baseUrl}/auth/resend-verification/`, {});
  }

  getToken(): string | null {
    return this._accessToken;
  }

  // ── Helpers privés ────────────────────────────────────────────────────────

  private _readCollaboratorIdFromToken(): number | null {
    if (!this._accessToken) return null;
    try {
      const payload = JSON.parse(atob(this._accessToken.split('.')[1]));
      if (payload.auth_type === 'collaborator' && payload.collaborator_id) {
        return Number(payload.collaborator_id);
      }
    } catch {}
    return null;
  }

  private _getSessionInfo(): Record<string, any> | null {
    try {
      const match = document.cookie.split('; ').find(r => r.startsWith('session_info='));
      if (!match) return null;
      return JSON.parse(decodeURIComponent(match.slice('session_info='.length)));
    } catch {
      return null;
    }
  }
}
