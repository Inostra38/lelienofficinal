import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { AdminAuthService } from '../../admin-auth.service';
import { Router } from '@angular/router';

@Component({
  selector: 'app-admin-layout',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './admin-layout.component.html',
})
export class AdminLayoutComponent {
  private auth = inject(AdminAuthService);
  private router = inject(Router);

  navItems = [
    { label: 'Statistiques', icon: 'chart', route: '/admin/statistiques' },
    { label: 'Ressources', icon: 'grid', route: '/admin/ressources' },
    { label: 'Recommandations', icon: 'star', route: '/admin/recommandations' },
  ];

  logout() {
    this.auth.logout().subscribe({
      next: () => this.router.navigate(['/admin/login']),
      error: () => this.router.navigate(['/admin/login']),
    });
  }
}
