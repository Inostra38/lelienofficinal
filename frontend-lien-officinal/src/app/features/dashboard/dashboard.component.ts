import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { AuthService } from '../../core/auth/auth.service'; // <-- Import indispensable

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css'
})
export class DashboardComponent implements OnInit {
  // On injecte le client HTTP pour parler à Django
  private http = inject(HttpClient);
  
  // On injecte le service d'Auth pour gérer la déconnexion
  private authService = inject(AuthService);

  categories: any[] = [];
  isLoading = true;

  ngOnInit() {
    // Appel API vers Django.
    // NOTE : Grâce à l'intercepteur qu'on a créé (auth.interceptor.ts),
    // le Token est ajouté automatiquement dans l'en-tête de cette requête.
    this.http.get<any>('http://127.0.0.1:8000/api/categories/')
      .subscribe({
        next: (data) => {
          console.log('✅ Dashboard chargé :', data);
          // On gère les deux formats possibles (Liste simple ou Pagination Django)
          this.categories = Array.isArray(data) ? data : data.results || [];
          this.isLoading = false;
        },
        error: (err) => {
          console.error('❌ Erreur chargement dashboard :', err);
          this.isLoading = false;
        }
      });
  }

  // Cette méthode est appelée quand on clique sur le bouton "Déconnexion" dans le HTML
  logout() {
    this.authService.logout();
  }
}
