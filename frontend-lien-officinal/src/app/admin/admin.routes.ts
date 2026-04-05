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
    path: 'change-password',
    loadComponent: () =>
      import('./pages/admin-change-password/admin-change-password.component').then(m => m.AdminChangePasswordComponent),
    canActivate: [adminAuthGuard],
  },
  {
    path: 'totp-setup',
    loadComponent: () =>
      import('./pages/admin-totp-setup/admin-totp-setup.component').then(m => m.AdminTotpSetupComponent),
    canActivate: [adminAuthGuard],
  },
  {
    path: '',
    loadComponent: () =>
      import('./components/admin-layout/admin-layout.component').then(m => m.AdminLayoutComponent),
    canActivate: [adminAuthGuard],
    children: [
      {
        path: 'statistiques',
        loadComponent: () =>
          import('./pages/admin-dashboard/admin-dashboard.component').then(m => m.AdminDashboardComponent),
      },
      {
        path: 'ressources',
        loadComponent: () =>
          import('./pages/admin-resources/admin-resources.component').then(m => m.AdminResourcesComponent),
      },
      {
        path: 'recommandations',
        loadComponent: () =>
          import('./pages/admin-recommendations/admin-recommendations.component').then(m => m.AdminRecommendationsComponent),
      },
      {
        path: '',
        redirectTo: 'statistiques',
        pathMatch: 'full',
      },
    ],
  },
];
