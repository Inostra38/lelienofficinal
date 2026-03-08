import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service'; // <-- Import

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './login.component.html',
  styleUrl: './login.component.css'
})
export class LoginComponent {
  private authService = inject(AuthService); // On utilise le service
  private router = inject(Router);

  email = '';
  password = '';
  isLoading = false;
  errorMessage = '';

  onSubmit(event: Event) {
    event.preventDefault();
    this.isLoading = true;
    this.errorMessage = '';

    const credentials = { email: this.email, password: this.password };

    this.authService.login(credentials).subscribe({
      next: () => {
        // ✅ Succès : On part vers le dashboard sécurisé
        this.router.navigate(['/dashboard']);
      },
      error: (err) => {
        console.error(err);
        this.errorMessage = "Email ou mot de passe incorrect.";
        this.isLoading = false;
      }
    });
  }
}