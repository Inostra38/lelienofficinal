import { Routes } from '@angular/router';
import { LoginComponent } from './features/login/login.component';
import { DashboardComponent } from './features/dashboard/dashboard.component';
import { authGuard } from './core/auth/auth.guard'; // <-- Import du videur

export const routes: Routes = [
  { path: 'login', component: LoginComponent },
  
  { 
    path: 'dashboard', 
    component: DashboardComponent,
    canActivate: [authGuard] // 🔒 PROTECTION ACTIVÉE ICI
  },
  
  // Par défaut, on essaie d'aller au dashboard (le guard redirigera si besoin)
  { path: '', redirectTo: 'dashboard', pathMatch: 'full' }
];