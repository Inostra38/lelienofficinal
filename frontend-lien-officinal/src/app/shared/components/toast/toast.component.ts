import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ToastService, Toast } from '../../../core/services/toast.service';

@Component({
  selector: 'app-toast',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
      @for (toast of toastService.toasts$ | async; track toast.id) {
        <div class="pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-xl shadow-lg text-sm font-medium min-w-64 max-w-sm animate-slide-in"
             [class]="toastClass(toast)">
          <span class="flex-1">{{ toast.message }}</span>
          <button (click)="toastService.dismiss(toast.id)"
                  class="opacity-60 hover:opacity-100 transition-opacity flex-shrink-0">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>
      }
    </div>
  `,
  styles: [`
    @keyframes slide-in {
      from { transform: translateX(100%); opacity: 0; }
      to   { transform: translateX(0);    opacity: 1; }
    }
    .animate-slide-in { animation: slide-in 0.2s ease-out; }
  `],
})
export class ToastComponent {
  toastService = inject(ToastService);

  toastClass(toast: Toast): string {
    const base = 'border ';
    switch (toast.type) {
      case 'success': return base + 'bg-green-50 border-green-200 text-green-800';
      case 'error':   return base + 'bg-red-50 border-red-200 text-red-800';
      case 'warning': return base + 'bg-amber-50 border-amber-200 text-amber-800';
      default:        return base + 'bg-gray-50 border-gray-200 text-gray-800';
    }
  }
}
