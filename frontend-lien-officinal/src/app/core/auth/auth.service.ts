import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Router } from '@angular/router';
import { BehaviorSubject } from 'rxjs';
import { tap, switchMap } from 'rxjs/operators';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private http = inject(HttpClient);
  private router = inject(Router);
  private baseUrl = 'http://127.0.0.1:8000/api';
  private tokenKey = 'access_token';
  private pharmacyTokenKey = 'pharmacy_access_token';
  private onboardingKey = 'onboarding_completed';
  private collaboratorKey = 'active_collaborator_id';

  private collaboratorSubject = new BehaviorSubject<number | null>(
    this._readCollaboratorIdFromToken() ?? this._readCollaboratorIdFromStorage()
  );
  readonly collaborator$ = this.collaboratorSubject.asObservable();

  login(credentials: any) {
    return this.http.post<any>(`${this.baseUrl}/token/`, credentials).pipe(
      tap(response => {
        localStorage.setItem(this.tokenKey, response.access);
        // Assurer qu'il n'y a pas de session collaborateur résiduelle
        localStorage.removeItem(this.pharmacyTokenKey);
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
    localStorage.removeItem(this.pharmacyTokenKey);
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
        }
        // Remplacer le token actif par le token collaborateur
        localStorage.setItem(this.tokenKey, response.access);
        this.collaboratorSubject.next(collaboratorId);
      })
    );
  }

  clearCurrentCollaborator(): void {
    // Restaurer le token pharmacie
    const pharmacyToken = localStorage.getItem(this.pharmacyTokenKey);
    if (pharmacyToken) {
      localStorage.setItem(this.tokenKey, pharmacyToken);
      localStorage.removeItem(this.pharmacyTokenKey);
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
