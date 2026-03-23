import { Component, inject } from '@angular/core';
import { ConfirmService } from '../../../core/services/confirm.service';

@Component({
  selector: 'app-confirm-modal',
  standalone: true,
  template: `
    @if (cs.visible) {
      <div class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
           (click)="cs.cancel()">
        <div class="bg-white rounded-2xl shadow-2xl w-full max-w-sm overflow-hidden"
             (click)="$event.stopPropagation()">

          <div class="px-6 pt-6 pb-4">
            <h3 class="text-base font-semibold text-gray-900 mb-2">{{ cs.title }}</h3>
            <p class="text-sm text-gray-500 leading-relaxed">{{ cs.message }}</p>
          </div>

          <div class="flex gap-3 px-6 pb-6 justify-end">
            <button (click)="cs.cancel()"
                    class="px-4 py-2 text-sm text-gray-600 border border-gray-200 rounded-xl hover:bg-gray-50 transition-colors">
              Annuler
            </button>
            <button (click)="cs.confirm()"
                    class="px-4 py-2 text-sm font-medium text-white rounded-xl transition-colors"
                    [class]="cs.danger ? 'bg-red-600 hover:bg-red-700' : 'bg-green-700 hover:bg-green-800'">
              {{ cs.confirmLabel }}
            </button>
          </div>

        </div>
      </div>
    }
  `,
})
export class ConfirmModalComponent {
  cs = inject(ConfirmService);
}
