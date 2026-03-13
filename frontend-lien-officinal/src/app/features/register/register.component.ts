import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './register.component.html',
})
export class RegisterComponent {
  private authService = inject(AuthService);
  private router = inject(Router);

  email = '';
  password = '';
  passwordConfirm = '';
  isLoading = false;
  errorMessage = '';

  get passwordMismatch(): boolean {
    return this.passwordConfirm.length > 0 && this.password !== this.passwordConfirm;
  }

  get isValid(): boolean {
    return (
      this.email.trim().length > 0 &&
      this.password.length >= 8 &&
      this.password === this.passwordConfirm
    );
  }

  onSubmit(event: Event) {
    event.preventDefault();
    if (!this.isValid || this.isLoading) return;

    this.isLoading = true;
    this.errorMessage = '';

    this.authService.register({
      email: this.email.trim(),
      password: this.password,
      password_confirm: this.passwordConfirm,
    }).subscribe({
      next: () => {
        this.router.navigate(['/onboarding']);
      },
      error: (err) => {
        this.isLoading = false;
        const data = err.error;
        if (data?.email) {
          this.errorMessage = 'Cette adresse email est déjà utilisée.';
        } else if (data?.password) {
          this.errorMessage = data.password[0];
        } else {
          this.errorMessage = 'Une erreur est survenue. Veuillez réessayer.';
        }
      }
    });
  }
}
