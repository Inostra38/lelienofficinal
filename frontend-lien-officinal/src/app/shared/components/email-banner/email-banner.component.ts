import { Component, inject, signal } from '@angular/core';
import { AuthService } from '../../../core/auth/auth.service';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-email-banner',
  standalone: true,
  imports: [CommonModule],
  template: `
    @if (!auth.isEmailVerified() && !dismissed()) {
      <div class="bg-amber-50 border-b border-amber-200 px-4 py-2 flex items-center justify-between text-sm">
        <span class="text-amber-800">
          @if (sent()) {
            Email envoyé ! Vérifiez votre boîte de réception.
          } @else if (rateLimited()) {
            Trop de demandes. Réessayez dans quelques heures.
          } @else {
            Votre adresse email n'est pas encore vérifiée. Certaines actions sont désactivées.
          }
        </span>
        <div class="flex items-center gap-3">
          @if (!sent() && !rateLimited()) {
            <button (click)="resend()" [disabled]="sending()"
              class="text-green-700 font-medium hover:underline disabled:opacity-50">
              {{ sending() ? 'Envoi…' : "Renvoyer l'email" }}
            </button>
          }
          <button (click)="dismissed.set(true)" class="text-amber-500 hover:text-amber-700">&#x2715;</button>
        </div>
      </div>
    }
  `
})
export class EmailBannerComponent {
  auth = inject(AuthService);
  dismissed = signal(false);
  sending = signal(false);
  sent = signal(false);
  rateLimited = signal(false);

  resend() {
    this.sending.set(true);
    this.auth.resendVerification().subscribe({
      next: () => {
        this.sending.set(false);
        this.sent.set(true);
      },
      error: (err) => {
        this.sending.set(false);
        if (err?.status === 429) {
          this.rateLimited.set(true);
        }
      }
    });
  }
}
