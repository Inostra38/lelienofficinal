import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { tap } from 'rxjs/operators';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private http = inject(HttpClient);
  private router = inject(Router);
  private apiUrl = 'http://127.0.0.1:8000/api/token/';
  private tokenKey = 'access_token';

  // 1. Se connecter et stocker le token
  login(credentials: any) {
    return this.http.post<any>(this.apiUrl, credentials).pipe(
      tap(response => {
        localStorage.setItem(this.tokenKey, response.access);
      })
    );
  }

  // 2. Se déconnecter (On jette le token et on renvoie au login)
  logout() {
    localStorage.removeItem(this.tokenKey);
    this.router.navigate(['/login']);
  }

  // 3. Est-ce qu'on est connecté ? (Vérification simple)
  isAuthenticated(): boolean {
    const token = localStorage.getItem(this.tokenKey);
    // Plus tard, on vérifiera l'expiration du token ici
    return !!token; 
  }

  // 4. Récupérer le token (pour les requêtes API futures)
  getToken(): string | null {
    return localStorage.getItem(this.tokenKey);
  }
}