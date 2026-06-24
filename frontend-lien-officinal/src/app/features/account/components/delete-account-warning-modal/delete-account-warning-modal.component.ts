import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-delete-account-warning-modal',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
         (click)="cancelled.emit()">
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden max-h-[90vh] flex flex-col"
           (click)="$event.stopPropagation()">

        <!-- En-tête rouge -->
        <div class="bg-red-50 border-b border-red-100 px-6 py-5 flex items-start gap-4">
          <div class="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0 mt-0.5">
            <svg class="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
            </svg>
          </div>
          <div>
            <h3 class="text-base font-semibold text-red-800">Supprimer mon compte</h3>
            <p class="text-sm text-red-600 mt-0.5">Action <strong>irréversible</strong> à l'échéance.</p>
          </div>
        </div>

        <!-- Corps (scrollable) -->
        <div class="px-6 py-5 overflow-y-auto">
          <p class="text-sm text-gray-700 mb-3">
            Votre compte sera supprimé <strong>à la fin de votre période d'abonnement</strong>
            (ou sous 30 jours si vous n'avez pas d'abonnement actif). Vous gardez l'accès jusque-là
            et pouvez annuler à tout moment d'ici cette date.
          </p>

          <p class="text-sm text-gray-700 mb-2">Seront <strong>définitivement effacées</strong> :</p>
          <ul class="space-y-1.5 text-sm text-gray-600 mb-4">
            <li class="flex items-center gap-2"><span class="w-1.5 h-1.5 rounded-full bg-red-400 flex-shrink-0"></span>Profil de la pharmacie et paramètres</li>
            <li class="flex items-center gap-2"><span class="w-1.5 h-1.5 rounded-full bg-red-400 flex-shrink-0"></span>Collaborateurs, ressources, tableau de bord</li>
            <li class="flex items-center gap-2"><span class="w-1.5 h-1.5 rounded-full bg-red-400 flex-shrink-0"></span>Messages, planning, procédures qualité, tâches</li>
            <li class="flex items-center gap-2"><span class="w-1.5 h-1.5 rounded-full bg-red-400 flex-shrink-0"></span>Crédits SMS restants (perdus)</li>
          </ul>

          <!-- Rappel factures -->
          <div class="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2.5 text-xs text-amber-800 mb-5 flex items-start gap-2">
            <span class="flex-shrink-0">⚠️</span>
            <span>Vos <strong>factures</strong> ne vous seront plus accessibles après la suppression
            (conservées uniquement pour nos obligations légales). <strong>Pensez à les télécharger</strong>
            depuis l'onglet Facturation avant de confirmer.</span>
          </div>

          <!-- Confirmation par saisie -->
          <label class="block text-sm font-medium text-gray-700 mb-1">
            Pour confirmer, tapez <span class="font-mono font-semibold text-red-600">je supprime</span>
          </label>
          <input type="text" [(ngModel)]="confirmPhrase" autocomplete="off" spellcheck="false"
                 placeholder="je supprime"
                 class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-3
                        focus:outline-none focus:ring-2 focus:ring-red-400">

          <label class="block text-sm font-medium text-gray-700 mb-1">Votre mot de passe</label>
          <input type="password" [(ngModel)]="password" autocomplete="current-password"
                 placeholder="Mot de passe du titulaire"
                 class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm
                        focus:outline-none focus:ring-2 focus:ring-red-400">

          @if (errorMessage) {
            <p class="text-sm text-red-600 mt-3">{{ errorMessage }}</p>
          }
        </div>

        <!-- Actions -->
        <div class="flex gap-3 px-6 pb-6 pt-1 justify-end border-t border-gray-50">
          <button (click)="cancelled.emit()" [disabled]="loading"
                  class="px-4 py-2 text-sm text-gray-600 border border-gray-200 rounded-xl hover:bg-gray-50 transition-colors disabled:opacity-50">
            Annuler
          </button>
          <button (click)="submit()" [disabled]="!canConfirm"
                  class="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-xl transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
            {{ loading ? 'Traitement...' : 'Programmer la suppression' }}
          </button>
        </div>

      </div>
    </div>
  `,
})
export class DeleteAccountWarningModalComponent {
  @Input() errorMessage = '';
  @Input() loading = false;
  @Output() confirmed = new EventEmitter<string>();   // émet le mot de passe
  @Output() cancelled = new EventEmitter<void>();

  readonly REQUIRED = 'je supprime';
  confirmPhrase = '';
  password = '';

  get canConfirm(): boolean {
    return (
      this.confirmPhrase.trim().toLowerCase() === this.REQUIRED &&
      this.password.length > 0 &&
      !this.loading
    );
  }

  submit(): void {
    if (this.canConfirm) {
      this.confirmed.emit(this.password);
    }
  }
}
