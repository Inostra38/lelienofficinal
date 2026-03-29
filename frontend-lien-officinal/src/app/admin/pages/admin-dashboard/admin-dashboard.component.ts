import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-admin-dashboard',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="min-h-screen flex items-center justify-center bg-gray-50">
      <p class="text-gray-600 text-sm">Dashboard admin — à construire</p>
    </div>
  `,
})
export class AdminDashboardComponent {}
