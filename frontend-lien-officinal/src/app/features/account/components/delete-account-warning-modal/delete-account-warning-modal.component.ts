import { Component, Output, EventEmitter } from '@angular/core';

@Component({
  selector: 'app-delete-account-warning-modal',
  standalone: true,
  template: `
    <div class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
         (click)="cancelled.emit()">
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden"
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
            <h3 class="text-base font-semibold text-red-800">Suppression définitive du compte</h3>
            <p class="text-sm text-red-600 mt-0.5">Cette action est <strong>irréversible</strong>. Aucune récupération possible.</p>
          </div>
        </div>

        <!-- Corps -->
        <div class="px-6 py-5">
          <p class="text-sm text-gray-700 mb-4">Les données suivantes seront <strong>définitivement supprimées</strong> :</p>
          <ul class="space-y-2 text-sm text-gray-600">
            <li class="flex items-center gap-2">
              <span class="w-1.5 h-1.5 rounded-full bg-red-400 flex-shrink-0"></span>
              Profil de la pharmacie et paramètres
            </li>
            <li class="flex items-center gap-2">
              <span class="w-1.5 h-1.5 rounded-full bg-red-400 flex-shrink-0"></span>
              Tous les collaborateurs et leurs données
            </li>
            <li class="flex items-center gap-2">
              <span class="w-1.5 h-1.5 rounded-full bg-red-400 flex-shrink-0"></span>
              Toutes les ressources et le tableau de bord
            </li>
            <li class="flex items-center gap-2">
              <span class="w-1.5 h-1.5 rounded-full bg-red-400 flex-shrink-0"></span>
              Tous les messages et conversations
            </li>
            <li class="flex items-center gap-2">
              <span class="w-1.5 h-1.5 rounded-full bg-red-400 flex-shrink-0"></span>
              Le planning, les procédures qualité et les tâches
            </li>
          </ul>
        </div>

        <!-- Actions -->
        <div class="flex gap-3 px-6 pb-6 justify-end">
          <button (click)="cancelled.emit()"
                  class="px-4 py-2 text-sm text-gray-600 border border-gray-200 rounded-xl hover:bg-gray-50 transition-colors">
            Annuler
          </button>
          <button (click)="confirmed.emit()"
                  class="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-xl transition-colors">
            Je comprends, continuer
          </button>
        </div>

      </div>
    </div>
  `,
})
export class DeleteAccountWarningModalComponent {
  @Output() confirmed = new EventEmitter<void>();
  @Output() cancelled = new EventEmitter<void>();
}
