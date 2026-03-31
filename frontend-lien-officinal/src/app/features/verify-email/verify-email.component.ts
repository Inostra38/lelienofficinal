import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-verify-email',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="min-h-screen flex items-center justify-center bg-gray-50">
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-10 max-w-md w-full text-center">
        @if (status() === 'loading') {
          <div class="text-gray-500">Vérification en cours…</div>
        }
        @if (status() === 'success') {
          <div class="text-green-700 font-semibold text-lg">Email vérifié avec succès !</div>
          <p class="text-gray-500 mt-2 text-sm">Vous pouvez maintenant utiliser toutes les fonctionnalités.</p>
          <button (click)="goToDashboard()"
            class="mt-6 bg-green-700 text-white px-6 py-2 rounded-lg text-sm font-medium hover:bg-green-800 transition">
            Accéder au tableau de bord
          </button>
        }
        @if (status() === 'error') {
          <div class="text-red-600 font-semibold text-lg">Lien invalide ou expiré</div>
          <p class="text-gray-500 mt-2 text-sm">{{ errorMessage() }}</p>
        }
      </div>
    </div>
  `
})
export class VerifyEmailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private auth = inject(AuthService);

  status = signal<'loading' | 'success' | 'error'>('loading');
  errorMessage = signal('');

  ngOnInit() {
    const token = this.route.snapshot.queryParamMap.get('token') ?? '';
    if (!token) {
      this.status.set('error');
      this.errorMessage.set('Token manquant dans le lien.');
      return;
    }

    this.auth.verifyEmail(token).subscribe({
      next: () => {
        this.auth.setEmailVerified();
        this.status.set('success');
      },
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
