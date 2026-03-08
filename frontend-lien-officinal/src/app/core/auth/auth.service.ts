import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Router } from '@angular/router';
import { tap, switchMap } from 'rxjs/operators';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private http = inject(HttpClient);
  private router = inject(Router);
  private baseUrl = 'http://127.0.0.1:8000/api';
  private tokenKey = 'access_token';
  private onboardingKey = 'onboarding_completed';
  private collaboratorKey = 'active_collaborator_id';

  login(credentials: any) {
    return this.http.post<any>(`${this.baseUrl}/token/`, credentials).pipe(
      tap(response => {
        localStorage.setItem(this.tokenKey, response.access);
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

  logout() {
    localStorage.removeItem(this.tokenKey);
    localStorage.removeItem(this.onboardingKey);
    localStorage.removeItem(this.collaboratorKey);
    this.router.navigate(['/login']);
  }

  // ── Collaborateur actif (partagé dashboard + messagerie) ─────────────────

  setCurrentCollaboratorId(id: number): void {
    localStorage.setItem(this.collaboratorKey, String(id));
  }

  getCurrentCollaboratorId(): number | null {
    const id = localStorage.getItem(this.collaboratorKey);
    return id ? Number(id) : null;
  }

  clearCurrentCollaborator(): void {
    localStorage.removeItem(this.collaboratorKey);
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
}