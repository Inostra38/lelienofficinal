import { Component, inject, ViewChildren, QueryList, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { AdminAuthService } from '../../admin-auth.service';

type Step = 'credentials' | 'totp';

@Component({
  selector: 'app-admin-login',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './admin-login.component.html',
})
export class AdminLoginComponent {
  private adminAuthService = inject(AdminAuthService);
  private router = inject(Router);

  @ViewChildren('totpInput') totpInputs!: QueryList<ElementRef<HTMLInputElement>>;

  // Étape 1
  email = '';
  password = '';

  // Étape 2
  totpDigits = ['', '', '', '', '', ''];
  sessionToken = '';
  totpConfigured = true;

  step: Step = 'credentials';
  isLoading = false;
  errorMessage = '';

  // ── Étape 1 ──────────────────────────────────────────────────────────────

  onSubmitCredentials(event: Event): void {
    event.preventDefault();
    this.isLoading = true;
    this.errorMessage = '';

    this.adminAuthService.login(this.email, this.password).subscribe({
      next: (res) => {
        this.sessionToken = res.session_token;
        this.totpConfigured = res.totp_configured;
        this.isLoading = false;

        if (!res.totp_configured) {
          // TOTP pas encore configuré : on soumet directement avec code vide
          this.step = 'totp';
          setTimeout(() => this.submitTotp(), 50);
        } else {
          this.step = 'totp';
          setTimeout(() => this.totpInputs?.first?.nativeElement?.focus(), 50);
        }
      },
      error: (err: HttpErrorResponse) => {
        this.isLoading = false;
        if (err.status === 403) {
          this.errorMessage = 'Accès non autorisé depuis cette adresse IP.';
        } else {
          this.errorMessage = 'Identifiants incorrects.';
        }
      },
    });
  }

  // ── Étape 2 ──────────────────────────────────────────────────────────────

  onTotpInput(event: Event, index: number): void {
    const input = event.target as HTMLInputElement;
    const value = input.value.replace(/\D/g, '').slice(-1);
    this.totpDigits[index] = value;
    input.value = value;

    if (value && index < 5) {
      this.totpInputs.toArray()[index + 1]?.nativeElement?.focus();
    }

    if (this.totpDigits.every(d => d !== '')) {
      this.submitTotp();
    }
  }

  onTotpKeydown(event: KeyboardEvent, index: number): void {
    if (event.key === 'Backspace' && !this.totpDigits[index] && index > 0) {
      this.totpInputs.toArray()[index - 1]?.nativeElement?.focus();
    }
  }

  onTotpPaste(event: ClipboardEvent): void {
    event.preventDefault();
    const text = event.clipboardData?.getData('text') ?? '';
    const digits = text.replace(/\D/g, '').slice(0, 6).split('');
    digits.forEach((d, i) => { this.totpDigits[i] = d; });
    const inputs = this.totpInputs.toArray();
    inputs.forEach((inp, i) => { inp.nativeElement.value = this.totpDigits[i] ?? ''; });
    const nextEmpty = digits.length < 6 ? digits.length : 5;
    inputs[nextEmpty]?.nativeElement?.focus();
    if (digits.length === 6) this.submitTotp();
  }

  private submitTotp(): void {
    const code = this.totpDigits.join('');
    this.isLoading = true;
    this.errorMessage = '';

    this.adminAuthService.verifyTotp(this.sessionToken, code).subscribe({
      next: () => {
        this.router.navigate(['/admin']);
      },
      error: () => {
        this.isLoading = false;
        this.errorMessage = 'Code incorrect ou expiré.';
        this.totpDigits = ['', '', '', '', '', ''];
        const inputs = this.totpInputs?.toArray();
        if (inputs) inputs.forEach(inp => inp.nativeElement.value = '');
        setTimeout(() => this.totpInputs?.first?.nativeElement?.focus(), 50);
      },
    });
  }

  onSubmitTotp(event: Event): void {
    event.preventDefault();
    this.submitTotp();
  }
}
