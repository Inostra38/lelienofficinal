import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { environment } from '../../../environments/environment';

@Component({
  selector: 'app-confirm-email-change',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="min-h-screen flex items-center justify-center bg-gray-50">
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-10 max-w-md w-full text-center">
        @if (status() === 'loading') {
          <div class="text-gray-500">Confirmation en cours…</div>
        }
        @if (status() === 'success') {
          <div class="text-green-700 font-semibold text-lg">Email mis à jour avec succès !</div>
          <p class="text-gray-500 mt-2 text-sm">Votre nouvelle adresse email est désormais active.</p>
          <button (click)="goToDashboard()"
            class="mt-6 bg-green-700 text-white px-6 py-2 rounded-lg text-sm font-medium hover:bg-green-800 transition">
            Retour au tableau de bord
          </button>
        }
        @if (status() === 'error') {
          <div class="text-red-600 font-semibold text-lg">Lien invalide ou expiré</div>
          <p class="text-gray-500 mt-2 text-sm">{{ errorMessage() }}</p>
          <p class="text-gray-400 mt-2 text-xs">Votre ancien email a été conservé. Vous pouvez effectuer une nouvelle demande depuis vos paramètres.</p>
        }
      </div>
    </div>
  `
})
export class ConfirmEmailChangeComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private http = inject(HttpClient);

  status = signal<'loading' | 'success' | 'error'>('loading');
  errorMessage = signal('');

  ngOnInit() {
    const token = this.route.snapshot.queryParamMap.get('token') ?? '';
    if (!token) {
      this.status.set('error');
      this.errorMessage.set('Token manquant dans le lien.');
      return;
    }

    this.http.post(`${environment.apiUrl}/api/account/confirm-email-change/`, { token }).subscribe({
      next: () => this.status.set('success'),
      error: (err) => {
        this.status.set('error');
        this.errorMessage.set(err?.error?.detail ?? 'Une erreur est survenue.');
      }
    });
  }

  goToDashboard() {
    this.router.navigate(['/dashboard']);
  }
}
