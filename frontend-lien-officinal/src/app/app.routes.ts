import { Routes } from '@angular/router';
import { LoginComponent } from './features/login/login.component';
import { RegisterComponent } from './features/register/register.component';
import { DashboardComponent } from './features/dashboard/dashboard.component';
import { AccountComponent } from './features/account/account.component';
import { OnboardingComponent } from './features/onboarding/onboarding.component';
import { MessagingComponent } from './features/messaging/messaging.component';
import { TasksComponent } from './features/tasks/tasks.component';
import { PlanningComponent } from './features/planning/planning.component';
import { SmsDashboardComponent } from './features/sms/sms-dashboard.component';
import { SmsSettingsComponent } from './features/sms/sms-settings.component';
import { MainLayoutComponent } from './shared/layouts/main-layout/main-layout.component';
import { authGuard } from './core/auth/auth.guard';
import { noAuthGuard } from './core/auth/no-auth.guard';
import { onboardingGuard } from './core/auth/onboarding.guard';
import { paidAccessGuard } from './core/auth/paid-access.guard';
import { qualityManagerGuard } from './core/auth/quality-manager.guard';
import { planningManagerGuard } from './core/auth/planning-manager.guard';
import { taskAssignerGuard } from './core/auth/task-assigner.guard';
import { ProcedureEditorComponent } from './features/quality/components/procedure-editor/procedure-editor.component';
import { ProcedureDetailComponent } from './features/quality/components/procedure-detail/procedure-detail.component';
import { NcListComponent } from './features/quality/components/nc-list/nc-list.component';
import { NcFormComponent } from './features/quality/components/nc-form/nc-form.component';
import { NcDetailComponent } from './features/quality/components/nc-detail/nc-detail.component';
import { ProcedureBoardsComponent } from './features/quality/components/procedure-boards/procedure-boards.component';
import { ProcedureArchivesComponent } from './features/quality/components/procedure-archives/procedure-archives.component';
import { SharedResourcesComponent } from './features/shared-resources/shared-resources.component';

export const routes: Routes = [
  // Module admin — isolé, lazy-loaded
  {
    path: 'admin',
    loadChildren: () => import('./admin/admin.routes').then(m => m.adminRoutes),
  },

  { path: 'login', component: LoginComponent, canActivate: [noAuthGuard] },
  { path: 'register', component: RegisterComponent, canActivate: [noAuthGuard] },
  {
    path: 'forgot-password',
    loadComponent: () =>
      import('./features/forgot-password/forgot-password.component').then(m => m.ForgotPasswordComponent)
  },
  {
    path: 'reset-password',
    loadComponent: () =>
      import('./features/reset-password/reset-password.component').then(m => m.ResetPasswordComponent)
  },
  { path: 'onboarding', component: OnboardingComponent, canActivate: [onboardingGuard] },
  {
    path: 'verify-email',
    loadComponent: () =>
      import('./features/verify-email/verify-email.component').then(m => m.VerifyEmailComponent)
  },
  {
    path: 'confirm-email-change',
    loadComponent: () =>
      import('./features/confirm-email-change/confirm-email-change.component').then(m => m.ConfirmEmailChangeComponent)
  },

  {
    path: '',
    component: MainLayoutComponent,
    canActivate: [authGuard],
    children: [
      { path: 'dashboard', component: DashboardComponent },
      { path: 'ressources-partagees', component: SharedResourcesComponent },
      { path: 'messagerie', component: MessagingComponent, canActivate: [paidAccessGuard] },
      { path: 'taches', component: TasksComponent, canActivate: [paidAccessGuard] },
      { path: 'planning', component: PlanningComponent, canActivate: [paidAccessGuard] },
      { path: 'account', component: AccountComponent },
      { path: 'sms', component: SmsDashboardComponent, canActivate: [paidAccessGuard] },
      { path: 'sms/settings', component: SmsSettingsComponent, canActivate: [paidAccessGuard] },
      { path: 'quality', component: ProcedureBoardsComponent, canActivate: [paidAccessGuard] },
      { path: 'quality/procedures/new', component: ProcedureEditorComponent, canActivate: [paidAccessGuard, qualityManagerGuard] },
      { path: 'quality/procedures/:id/edit', component: ProcedureEditorComponent, canActivate: [paidAccessGuard] },
      { path: 'quality/procedures/:id', component: ProcedureDetailComponent, canActivate: [paidAccessGuard] },
      { path: 'quality/nc', component: NcListComponent, canActivate: [paidAccessGuard] },
      { path: 'quality/nc/new', component: NcFormComponent, canActivate: [paidAccessGuard] },
      { path: 'quality/nc/:id', component: NcDetailComponent, canActivate: [paidAccessGuard] },
      { path: 'quality/archives', component: ProcedureArchivesComponent, canActivate: [paidAccessGuard] },
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' }
    ]
  }
];
