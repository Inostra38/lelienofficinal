import { Routes } from '@angular/router';
import { LoginComponent } from './features/login/login.component';
import { DashboardComponent } from './features/dashboard/dashboard.component';
import { AccountComponent } from './features/account/account.component';
import { OnboardingComponent } from './features/onboarding/onboarding.component';
import { MessagingComponent } from './features/messaging/messaging.component';
import { TasksComponent } from './features/tasks/tasks.component';
import { MainLayoutComponent } from './shared/layouts/main-layout/main-layout.component';
import { authGuard } from './core/auth/auth.guard';
import { noAuthGuard } from './core/auth/no-auth.guard';

export const routes: Routes = [
  { path: 'login', component: LoginComponent, canActivate: [noAuthGuard] },
  { path: 'onboarding', component: OnboardingComponent },

  {
    path: '',
    component: MainLayoutComponent,
    canActivate: [authGuard],
    children: [
      { path: 'dashboard', component: DashboardComponent },
      { path: 'messagerie', component: MessagingComponent },
      { path: 'taches', component: TasksComponent },
      { path: 'account', component: AccountComponent },
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' }
    ]
  }
];
