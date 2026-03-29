import { Routes } from '@angular/router';
import { adminAuthGuard, adminNoAuthGuard } from './admin-auth.guard';

export const adminRoutes: Routes = [
  {
    path: 'login',
    loadComponent: () =>
      import('./pages/admin-login/admin-login.component').then(m => m.AdminLoginComponent),
    canActivate: [adminNoAuthGuard],
  },
  {
    path: 'dashboard',
    loadComponent: () =>
      import('./pages/admin-dashboard/admin-dashboard.component').then(m => m.AdminDashboardComponent),
    canActivate: [adminAuthGuard],
  },
  {
    path: '',
    redirectTo: 'dashboard',
    pathMatch: 'full',
  },
];
