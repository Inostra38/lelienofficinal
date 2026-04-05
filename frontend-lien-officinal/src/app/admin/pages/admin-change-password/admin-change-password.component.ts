import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../../environments/environment';

@Component({
  selector: 'app-admin-change-password',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './admin-change-password.component.html',
})
export class AdminChangePasswordComponent {
  private http = inject(HttpClient);
  private router = inject(Router);

  oldPassword = '';
  newPassword = '';
  confirmPassword = '';
  saving = false;
  errorMessage = '';
  successMessage = '';

  get passwordErrors(): string[] {
    const errors: string[] = [];
    const p = this.newPassword;
    if (!p) return errors;
    if (p.length < 12) errors.push('12 caractères minimum');
    if (!/[A-Z]/.test(p)) errors.push('1 majuscule');
    if (!/[a-z]/.test(p)) errors.push('1 minuscule');
    if (!/\d/.test(p)) errors.push('1 chiffre');
    if (!/[^A-Za-z0-9]/.test(p)) errors.push('1 caractère spécial');
    return errors;
  }

  get isValid(): boolean {
    return (
      this.oldPassword.length > 0 &&
      this.newPassword.length >= 12 &&
      this.passwordErrors.length === 0 &&
      this.newPassword === this.confirmPassword &&
      this.newPassword !== this.oldPassword
    );
  }

  submit(): void {
    if (!this.isValid) return;
    this.saving = true;
    this.errorMessage = '';

    this.http.post<any>(`${environment.apiUrl}/api/admin/auth/change-password/`, {
      old_password: this.oldPassword,
      new_password: this.newPassword,
    }).subscribe({
      next: () => {
        this.saving = false;
        this.successMessage = 'Mot de passe modifié avec succès.';
        // Vérifier si TOTP est configuré via un ping
        setTimeout(() => {
          this.http.get(`${environment.apiUrl}/api/admin/resources/`).subscribe({
            next: () => this.router.navigate(['/admin']),
            error: (err) => {
              const body = typeof err.error === 'string' ? (() => { try { return JSON.parse(err.error); } catch { return {}; } })() : err.error;
              if (body?.code === 'totp_setup_required') {
                this.router.navigate(['/admin/totp-setup']);
              } else {
                this.router.navigate(['/admin']);
              }
            },
          });
        }, 1000);
      },
      error: (err) => {
        this.saving = false;
        if (err.error?.old_password) {
          this.errorMessage = err.error.old_password;
        } else if (err.error?.new_password) {
          this.errorMessage = Array.isArray(err.error.new_password)
            ? err.error.new_password.join(' ')
            : err.error.new_password;
        } else {
          this.errorMessage = 'Erreur lors du changement de mot de passe.';
        }
      },
    });
  }
}
