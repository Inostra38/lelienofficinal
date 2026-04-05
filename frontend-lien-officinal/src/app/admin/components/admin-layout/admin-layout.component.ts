import { Component, OnInit, OnDestroy, inject, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { AdminAuthService } from '../../admin-auth.service';
import { Router } from '@angular/router';
import { environment } from '../../../../environments/environment';

const INACTIVITY_TIMEOUT = 30 * 60 * 1000; // 30 minutes

@Component({
  selector: 'app-admin-layout',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './admin-layout.component.html',
})
export class AdminLayoutComponent implements OnInit, OnDestroy {
  private auth = inject(AdminAuthService);
  private router = inject(Router);
  private http = inject(HttpClient);
  private inactivityTimer: any = null;

  navItems = [
    { label: 'Statistiques', icon: 'chart', route: '/admin/statistiques' },
    { label: 'Ressources', icon: 'grid', route: '/admin/ressources' },
    { label: 'Recommandations', icon: 'star', route: '/admin/recommandations' },
  ];

  @HostListener('document:mousemove')
  @HostListener('document:keydown')
  @HostListener('document:click')
  onActivity() {
    this.resetInactivityTimer();
  }

  ngOnInit() {
    // Ping pour déclencher le guard middleware
    this.http.get(`${environment.apiUrl}/api/admin/resources/`).subscribe({
      next: () => {},
      error: () => {},
    });
    this.resetInactivityTimer();
  }

  ngOnDestroy() {
    if (this.inactivityTimer) {
      clearTimeout(this.inactivityTimer);
    }
  }

  private resetInactivityTimer() {
    if (this.inactivityTimer) {
      clearTimeout(this.inactivityTimer);
    }
    this.inactivityTimer = setTimeout(() => {
      this.logout();
    }, INACTIVITY_TIMEOUT);
  }

  logout() {
    if (this.inactivityTimer) {
      clearTimeout(this.inactivityTimer);
    }
    this.auth.logout().subscribe({
      next: () => this.router.navigate(['/admin/login']),
      error: () => this.router.navigate(['/admin/login']),
    });
  }
}
