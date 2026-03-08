import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../../../core/auth/auth.service';
import { OnboardingService } from '../../../../core/services/onboarding.service';

@Component({
  selector: 'app-step1-account',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './step1-account.component.html',
})
export class Step1AccountComponent {
  private auth = inject(AuthService);
  private onboarding = inject(OnboardingService);
  private router = inject(Router);

  email = '';
  password = '';
  passwordConfirm = '';
  error = '';
  loading = false;

  submit() {
    this.error = '';

    if (this.password !== this.passwordConfirm) {
      this.error = 'Les mots de passe ne correspondent pas.';
      return;
    }

    this.loading = true;
    this.auth.register({ email: this.email, password: this.password, password_confirm: this.passwordConfirm }).subscribe({
      next: () => {
        this.loading = false;
        this.onboarding.nextStep();
      },
      error: (err) => {
        this.loading = false;
        const data = err.error;
        if (data?.email) this.error = data.email[0];
        else if (data?.password) this.error = data.password[0];
        else this.error = 'Une erreur est survenue.';
      }
    });
  }
}
