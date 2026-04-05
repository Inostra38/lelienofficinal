import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-admin-dashboard',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="p-6 max-w-5xl mx-auto">
      <h1 class="text-xl font-bold text-gray-800 mb-1">Statistiques</h1>
      <p class="text-sm text-gray-400 mb-8">Vue d'ensemble de la plateforme</p>

      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div class="bg-white rounded-xl border border-gray-100 p-5">
          <p class="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">Pharmacies</p>
          <p class="text-2xl font-bold text-gray-800">—</p>
        </div>
        <div class="bg-white rounded-xl border border-gray-100 p-5">
          <p class="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">Ressources</p>
          <p class="text-2xl font-bold text-gray-800">—</p>
        </div>
        <div class="bg-white rounded-xl border border-gray-100 p-5">
          <p class="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">Recommandations en attente</p>
          <p class="text-2xl font-bold text-gray-800">—</p>
        </div>
      </div>

      <p class="text-xs text-gray-300 mt-6">Les statistiques seront alimentées prochainement.</p>
    </div>
  `,
})
export class AdminDashboardComponent {}
