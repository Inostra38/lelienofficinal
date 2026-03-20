import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Router } from '@angular/router';
import { BehaviorSubject, Observable, throwError } from 'rxjs';
import { tap, switchMap, map, filter, take, catchError } from 'rxjs/operators';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private http = inject(HttpClient);
  private router = inject(Router);
  private baseUrl = 'http://127.0.0.1:8000/api';
  private tokenKey = 'access_token';
  private refreshKey = 'refresh_token';
  private pharmacyTokenKey = 'pharmacy_access_token';
  private pharmacyRefreshKey = 'pharmacy_refresh_token';
  private onboardingKey = 'onboarding_completed';
  private collaboratorKey = 'active_collaborator_id';

  // Initialisation depuis le JWT uniquement — pas de fallback localStorage (évite les sessions fantômes)
  private collaboratorSubject = new BehaviorSubject<number | null>(
    this._readCollaboratorIdFromToken()
  );
  readonly collaborator$ = this.collaboratorSubject.asObservable();

  // Guard contre les refreshes simultanés (évite le blacklisting du refresh token)
  private isRefreshing = false;
  private refreshSubject = new BehaviorSubject<string | null>(null);

  login(credentials: any) {
    return this.http.post<any>(`${this.baseUrl}/token/`, credentials).pipe(
      tap(response => {
        localStorage.setItem(this.tokenKey, response.access);
        localStorage.setItem(this.refreshKey, response.refresh);
        localStorage.removeItem(this.pharmacyTokenKey);
        localStorage.removeItem(this.pharmacyRefreshKey);
        this.collaboratorSubject.next(null);
      }),
      switchMap(() => {
        const headers = new HttpHeaders({ Authorization: `Bearer ${this.getToken()}` });
        return this.http.get<any>(`${this.baseUrl}/pharmacy/me/`, { headers });
      }),
      tap(profile => {
        localStorage.setItem(this.onboardingKey, profile.onboarding_completed ? 'true' : 'false');
      })
    );
  }

  register(data: { email: string; password: string; password_confirm: string }) {
    return this.http.post<any>(`${this.baseUrl}/auth/register/`, data).pipe(
      tap(response => {
        localStorage.setItem(this.tokenKey, response.access);
        localStorage.setItem(this.onboardingKey, 'false');
      })
    );
  }

  logout(returnUrl?: string) {
    localStorage.removeItem(this.tokenKey);
    localStorage.removeItem(this.refreshKey);
    localStorage.removeItem(this.pharmacyTokenKey);
    localStorage.removeItem(this.pharmacyRefreshKey);
    localStorage.removeItem(this.onboardingKey);
    localStorage.removeItem(this.collaboratorKey);
    this.collaboratorSubject.next(null);
    this.router.navigate(['/login'], returnUrl ? { queryParams: { returnUrl } } : {});
  }

  // ── Session collaborateur ─────────────────────────────────────────────────

  /**
   * Échange un PIN contre un JWT collaborateur.
   * Sauvegarde le JWT pharmacie puis remplace le token actif.
   */
  collaboratorLogin(collaboratorId: number, pin: string) {
    return this.http.post<any>(`${this.baseUrl}/team/login/`, {
      collaborator_id: collaboratorId,
      pin_code: pin
    }).pipe(
      tap(response => {
        // Sauvegarder le token pharmacie si ce n'est pas déjà un token collaborateur
        if (this.getAuthType() !== 'collaborator') {
          const currentToken = this.getToken();
          if (currentToken) {
            localStorage.setItem(this.pharmacyTokenKey, currentToken);
          }
          const currentRefresh = this.getRefreshToken();
          if (currentRefresh) {
            localStorage.setItem(this.pharmacyRefreshKey, currentRefresh);
          }
        }
        // Remplacer le token actif par le token collaborateur
        localStorage.setItem(this.tokenKey, response.access);
        if (response.refresh) {
          localStorage.setItem(this.refreshKey, response.refresh);
        }
        this.collaboratorSubject.next(collaboratorId);
      })
    );
  }

  clearCurrentCollaborator(): void {
    // Restaurer le token pharmacie
    const pharmacyToken = localStorage.getItem(this.pharmacyTokenKey);
    const pharmacyRefresh = localStorage.getItem(this.pharmacyRefreshKey);
    if (pharmacyToken) {
      localStorage.setItem(this.tokenKey, pharmacyToken);
      localStorage.removeItem(this.pharmacyTokenKey);
    }
    if (pharmacyRefresh) {
      localStorage.setItem(this.refreshKey, pharmacyRefresh);
      localStorage.removeItem(this.pharmacyRefreshKey);
    }
    localStorage.removeItem(this.collaboratorKey);
    this.collaboratorSubject.next(null);
  }

  /** @deprecated Utiliser collaboratorLogin() à la place */
  setCurrentCollaboratorId(id: number): void {
    localStorage.setItem(this.collaboratorKey, String(id));
    this.collaboratorSubject.next(id);
  }

  getCurrentCollaboratorId(): number | null {
    // Lire depuis le JWT en priorité
    const fromToken = this._readCollaboratorIdFromToken();
    if (fromToken !== null) return fromToken;
    // Fallback localStorage (rétrocompatibilité)
    return this._readCollaboratorIdFromStorage();
  }

  // ── Refresh token ─────────────────────────────────────────────────────────

  refreshAccessToken(): Observable<string> {
    // Si un refresh est déjà en cours, on attend son résultat plutôt que d'en lancer un second
    // (évite le blacklisting du refresh token avec ROTATE_REFRESH_TOKENS=True)
    if (this.isRefreshing) {
      return this.refreshSubject.pipe(
        filter((token): token is string => token !== null),
        take(1)
      );
    }

    const refreshToken = this.getRefreshToken();
    if (!refreshToken) {
      return throwError(() => new Error('No refresh token'));
    }

    this.isRefreshing = true;
    this.refreshSubject.next(null);

    return this.http.post<any>(`${this.baseUrl}/token/refresh/`, { refresh: refreshToken }).pipe(
      tap(response => {
        localStorage.setItem(this.tokenKey, response.access);
        if (response.refresh) {
          localStorage.setItem(this.refreshKey, response.refresh);
        }
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
    return localStorage.getItem(this.refreshKey);
  }

  // ── Auth state ────────────────────────────────────────────────────────────

  /**
   * Vrai si l'utilisateur actuel peut gérer la qualité.
   * - Accès direct pharmacie (titulaire) → toujours vrai
   * - Collaborateur → lit le claim `can_manage_quality` du JWT
   */
  canManageQuality(): boolean {
    const token = this.getToken();
    if (!token) return false;
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      return payload.can_manage_quality === true;
    } catch {
      return false;
    }
  }

  getAuthType(): 'pharmacy_account' | 'collaborator' | null {
    const token = this.getToken();
    if (!token) return null;
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      return payload.auth_type ?? 'pharmacy_account';
    } catch {
      return null;
    }
  }

  isAuthenticated(): boolean {
    const token = localStorage.getItem(this.tokenKey);
    if (!token) return false;
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      return payload.exp * 1000 > Date.now();
    } catch {
      return false;
    }
  }

  isOnboardingCompleted(): boolean {
    return localStorage.getItem(this.onboardingKey) === 'true';
  }

  setOnboardingCompleted() {
    localStorage.setItem(this.onboardingKey, 'true');
  }

  getToken(): string | null {
    return localStorage.getItem(this.tokenKey);
  }

  // ── Helpers privés ────────────────────────────────────────────────────────

  private _readCollaboratorIdFromToken(): number | null {
    const token = localStorage.getItem(this.tokenKey);
    if (!token) return null;
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      if (payload.auth_type === 'collaborator' && payload.collaborator_id) {
        return Number(payload.collaborator_id);
      }
    } catch {}
    return null;
  }

  private _readCollaboratorIdFromStorage(): number | null {
    const id = localStorage.getItem(this.collaboratorKey);
    return id ? Number(id) : null;
  }
}
