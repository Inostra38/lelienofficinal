import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { AdminAuthService } from '../../admin-auth.service';
import { Router } from '@angular/router';
import { environment } from '../../../../environments/environment';

@Component({
  selector: 'app-admin-layout',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './admin-layout.component.html',
})
export class AdminLayoutComponent implements OnInit {
  private auth = inject(AdminAuthService);
  private router = inject(Router);
  private http = inject(HttpClient);

  navItems = [
    { label: 'Statistiques', icon: 'chart', route: '/admin/statistiques' },
    { label: 'Ressources', icon: 'grid', route: '/admin/ressources' },
    { label: 'Recommandations', icon: 'star', route: '/admin/recommandations' },
  ];

  ngOnInit() {
    // Ping un endpoint admin pour déclencher le guard middleware.
    // Si force_password_change ou totp manquant, l'interceptor redirigera.
    this.http.get(`${environment.apiUrl}/api/admin/resources/`).subscribe({
      next: () => {},
      error: () => {},
    });
  }

  logout() {
    this.auth.logout().subscribe({
      next: () => this.router.navigate(['/admin/login']),
      error: () => this.router.navigate(['/admin/login']),
    });
  }
}
