import { Routes } from '@angular/router';
import { LoginComponent } from './features/login/login.component';
import { DashboardComponent } from './features/dashboard/dashboard.component';
import { AccountComponent } from './features/account/account.component';
import { OnboardingComponent } from './features/onboarding/onboarding.component';
import { MessagingComponent } from './features/messaging/messaging.component';
import { TasksComponent } from './features/tasks/tasks.component';
import { authGuard } from './core/auth/auth.guard';

export const routes: Routes = [
  { path: 'login', component: LoginComponent },

  { path: 'onboarding', component: OnboardingComponent },

  {
    path: 'dashboard',
    component: DashboardComponent,
    canActivate: [authGuard]
  },

  {
    path: 'account',
    component: AccountComponent,
    canActivate: [authGuard]
  },

  {
    path: 'messagerie',
    component: MessagingComponent,
    canActivate: [authGuard]
  },

  {
    path: 'taches',
    component: TasksComponent,
    canActivate: [authGuard]
  },

  { path: '', redirectTo: 'dashboard', pathMatch: 'full' }
];