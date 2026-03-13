import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { AuthService } from '../../../../core/auth/auth.service';
import { ConfirmSensitiveActionModalComponent } from '../../../../shared/ui/confirm-sensitive-action-modal/confirm-sensitive-action-modal.component';
import { environment } from '../../../../../environments/environment';

@Component({
  selector: 'app-account-security',
  standalone: true,
  imports: [CommonModule, FormsModule, ConfirmSensitiveActionModalComponent],
  templateUrl: './account-security.component.html',
  styleUrl: './account-security.component.css'
})
export class AccountSecurityComponent {
  private http = inject(HttpClient);
  private authService = inject(AuthService);

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

  requestUnlock() {
    this.pinGateError = '';
    this.showPinGate = true;
  }

  onPinGateConfirmed(pin: string) {
    const token = localStorage.getItem('access_token');
    this.http.post(
      `${environment.apiUrl}/api/account/verify-security-access/`,
      { confirmation_pin: pin },
      { headers: new HttpHeaders({ Authorization: `Bearer ${token ?? ''}` }) }
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
    const token = localStorage.getItem('access_token');
    const refreshToken = localStorage.getItem('refresh_token');

    this.http.post(
      `${environment.apiUrl}/api/account/change-password/`,
      {
        old_password: this.oldPassword,
        new_password: this.newPassword,
        new_password_confirm: this.newPasswordConfirm,
        refresh_token: refreshToken ?? ''
      },
      { headers: new HttpHeaders({ Authorization: `Bearer ${token ?? ''}` }) }
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
    const token = localStorage.getItem('access_token');

    this.http.post(
      `${environment.apiUrl}/api/account/change-email/`,
      { new_email: this.newEmail, password: this.emailPassword },
      { headers: new HttpHeaders({ Authorization: `Bearer ${token ?? ''}` }) }
    ).subscribe({
      next: (res: any) => {
        this.isChangingEmail = false;
        this.emailSuccess = res.detail || 'Email mis à jour avec succès.';
        this.newEmail = '';
        this.emailPassword = '';
        setTimeout(() => { this.emailSuccess = ''; }, 5000);
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
