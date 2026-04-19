import { Component, inject, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink, ActivatedRoute } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-reset-password',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './reset-password.component.html',
})
export class ResetPasswordComponent implements OnInit {
  private authService = inject(AuthService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);

  token = '';
  password = '';
  passwordConfirm = '';
  isLoading = false;
  success = false;
  errorMessage = '';

  ngOnInit() {
    this.token = this.route.snapshot.queryParams['token'] || '';
    if (!this.token) {
      this.router.navigate(['/forgot-password']);
    }
  }

  get passwordsMatch(): boolean {
    return this.password === this.passwordConfirm;
  }

  onSubmit(event: Event) {
    event.preventDefault();
    if (!this.passwordsMatch) return;

    this.isLoading = true;
    this.errorMessage = '';

    this.authService.resetPassword(this.token, this.password).subscribe({
      next: () => {
        this.success = true;
        this.isLoading = false;
      },
      error: (err) => {
        const detail = err.error?.detail;
        if (Array.isArray(detail)) {
          this.errorMessage = detail.join(' ');
        } else {
          this.errorMessage = detail || 'Ce lien est invalide ou a expiré.';
        }
        this.isLoading = false;
      }
    });
  }
}
