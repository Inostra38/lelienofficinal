import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { AuthService } from '../../../../core/auth/auth.service';
import { PharmacyService } from '../../../../core/services/pharmacy.service';
import { ConfirmSensitiveActionModalComponent } from '../../../../shared/ui/confirm-sensitive-action-modal/confirm-sensitive-action-modal.component';
import { DeleteAccountWarningModalComponent } from '../delete-account-warning-modal/delete-account-warning-modal.component';
import { environment } from '../../../../../environments/environment';

@Component({
  selector: 'app-account-security',
  standalone: true,
  imports: [CommonModule, FormsModule, ConfirmSensitiveActionModalComponent, DeleteAccountWarningModalComponent],
  templateUrl: './account-security.component.html',
  styleUrl: './account-security.component.css'
})
export class AccountSecurityComponent implements OnInit {
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private pharmacyService = inject(PharmacyService);
  private router = inject(Router);

  pendingEmail = '';

  isUnlocked = false;
  showPinGate = false;
  pinGateError = '';

  readonly pinGateHint = 'le PIN d\'un membre autorisé';

  // Changer mot de passe
  oldPassword = '';
  newPassword = '';
  newPasswordConfirm = '';
  passwordError = '';
  passwordSuccess = '';
  isChangingPassword = false;

  // Changer email
  newEmail = '';
  emailPassword = '';
  emailError = '';
  emailSuccess = '';
  isChangingEmail = false;

  // Suppression du compte
  showDeleteWarning = false;
  showDeleteConfirm = false;
  deleteError = '';
  isDeletingAccount = false;

  ngOnInit() {
    this.pharmacyService.getCurrentPharmacy().subscribe({
      next: (p) => { this.pendingEmail = p.pending_email || ''; }
    });
  }

  requestUnlock() {
    this.pinGateError = '';
    this.showPinGate = true;
  }

  onPinGateConfirmed(pin: string) {
    // M6 : Authorization via authInterceptor.
    this.http.post(
      `${environment.apiUrl}/api/account/verify-security-access/`,
      { confirmation_pin: pin }
    ).subscribe({
      next: () => {
        this.isUnlocked = true;
        this.showPinGate = false;
        this.pinGateError = '';
      },
      error: (err) => {
        this.pinGateError = err.error?.detail || 'PIN incorrect.';
      }
    });
  }

  onPinGateCancelled() {
    this.showPinGate = false;
    this.pinGateError = '';
  }

  changePassword() {
    this.passwordError = '';
    this.passwordSuccess = '';

    if (!this.oldPassword) {
      this.passwordError = 'Veuillez saisir votre mot de passe actuel.';
      return;
    }
    if (this.newPassword.length < 8) {
      this.passwordError = 'Le nouveau mot de passe doit faire au moins 8 caractères.';
      return;
    }
    if (this.newPassword !== this.newPasswordConfirm) {
      this.passwordError = 'Les mots de passe ne correspondent pas.';
      return;
    }

    this.isChangingPassword = true;

    // M6 : Authorization via authInterceptor ; le refresh est géré côté serveur
    // via le cookie HttpOnly.
    this.http.post(
      `${environment.apiUrl}/api/account/change-password/`,
      {
        old_password: this.oldPassword,
        new_password: this.newPassword,
        new_password_confirm: this.newPasswordConfirm,
      }
    ).subscribe({
      next: () => {
        this.isChangingPassword = false;
        this.oldPassword = '';
        this.newPassword = '';
        this.newPasswordConfirm = '';
        this.authService.logout();
      },
      error: (err) => {
        this.isChangingPassword = false;
        const errors = err.error;
        if (errors?.old_password) {
          this.passwordError = Array.isArray(errors.old_password) ? errors.old_password[0] : errors.old_password;
        } else if (errors?.new_password) {
          this.passwordError = Array.isArray(errors.new_password) ? errors.new_password.join(' ') : errors.new_password;
        } else if (errors?.new_password_confirm) {
          this.passwordError = errors.new_password_confirm;
        } else {
          this.passwordError = errors?.detail || 'Erreur lors du changement de mot de passe.';
        }
      }
    });
  }

  onDeleteWarningConfirmed() {
    this.showDeleteWarning = false;
    this.deleteError = '';
    this.showDeleteConfirm = true;
  }

  deleteAccount(password: string) {
    this.isDeletingAccount = true;
    this.deleteError = '';
    // M6 : Authorization via authInterceptor.
    this.http.delete(
      `${environment.apiUrl}/api/account/delete/`,
      { body: { password } }
    ).subscribe({
      next: () => {
        this.authService.logout();
        this.router.navigate(['/login'], { queryParams: { deleted: 'true' } });
      },
      error: (err) => {
        this.isDeletingAccount = false;
        this.deleteError = err.error?.detail || 'Erreur lors de la suppression du compte.';
      },
    });
  }

  cancelEmailChange() {
    // M6 : Authorization via authInterceptor.
    this.http.post(
      `${environment.apiUrl}/api/account/cancel-email-change/`,
      {}
    ).subscribe({
      next: () => { this.pendingEmail = ''; }
    });
  }

  changeEmail() {
    this.emailError = '';
    this.emailSuccess = '';

    if (!this.newEmail || !this.newEmail.includes('@')) {
      this.emailError = 'Adresse email invalide.';
      return;
    }
    if (!this.emailPassword) {
      this.emailError = 'Veuillez saisir votre mot de passe pour confirmer.';
      return;
    }

    this.isChangingEmail = true;

    // M6 : Authorization via authInterceptor.
    this.http.post(
      `${environment.apiUrl}/api/account/change-email/`,
      { new_email: this.newEmail, password: this.emailPassword }
    ).subscribe({
      next: (res: any) => {
        this.isChangingEmail = false;
        this.emailSuccess = res.detail || 'Email de confirmation envoyé.';
        this.pendingEmail = this.newEmail;
        this.newEmail = '';
        this.emailPassword = '';
        setTimeout(() => { this.emailSuccess = ''; }, 8000);
      },
      error: (err) => {
        this.isChangingEmail = false;
        const errors = err.error;
        if (errors?.new_email) {
          this.emailError = Array.isArray(errors.new_email) ? errors.new_email[0] : errors.new_email;
        } else if (errors?.password) {
          this.emailError = Array.isArray(errors.password) ? errors.password[0] : errors.password;
        } else {
          this.emailError = errors?.detail || 'Erreur lors du changement d\'email.';
        }
      }
    });
  }
}
