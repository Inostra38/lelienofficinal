import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-forgot-password',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './forgot-password.component.html',
})
export class ForgotPasswordComponent {
  private authService = inject(AuthService);

  email = '';
  isLoading = false;
  submitted = false;
  errorMessage = '';

  onSubmit(event: Event) {
    event.preventDefault();
    this.isLoading = true;
    this.errorMessage = '';

    this.authService.forgotPassword(this.email).subscribe({
      next: () => {
        this.submitted = true;
        this.isLoading = false;
      },
      error: () => {
        this.errorMessage = 'Une erreur est survenue. Veuillez réessayer.';
        this.isLoading = false;
      }
    });
  }
}
