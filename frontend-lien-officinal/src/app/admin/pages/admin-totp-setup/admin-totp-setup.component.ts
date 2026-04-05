import { Component, OnInit, inject, ViewChild, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../../environments/environment';

@Component({
  selector: 'app-admin-totp-setup',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './admin-totp-setup.component.html',
})
export class AdminTotpSetupComponent implements OnInit {
  private http = inject(HttpClient);
  private router = inject(Router);

  @ViewChild('hiddenInput') hiddenInput!: ElementRef<HTMLInputElement>;

  qrBase64 = '';
  secret = '';
  otpauthUrl = '';
  loading = true;
  errorMessage = '';

  code = '';
  digits = ['', '', '', '', '', ''];
  confirming = false;
  successMessage = '';

  ngOnInit(): void {
    this.loadSetup();
  }

  loadSetup(): void {
    this.loading = true;
    this.http.get<any>(`${environment.apiUrl}/api/admin/auth/totp-setup/`).subscribe({
      next: (res) => {
        this.qrBase64 = res.qr_base64;
        this.otpauthUrl = res.otpauth_url;
        // Extraire le secret depuis l'otpauth URL pour affichage manuel
        const match = res.otpauth_url?.match(/secret=([A-Z2-7]+)/i);
        this.secret = match ? match[1] : '';
        this.loading = false;
        setTimeout(() => this.focusHiddenInput(), 100);
      },
      error: (err) => {
        this.loading = false;
        this.errorMessage = err.error?.detail || 'Erreur lors du chargement du QR code.';
      },
    });
  }

  focusHiddenInput(): void {
    this.hiddenInput?.nativeElement?.focus();
  }

  onCodeInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.code = input.value.replace(/\D/g, '').slice(0, 6);
    input.value = this.code;

    // Mettre à jour l'affichage visuel
    for (let i = 0; i < 6; i++) {
      this.digits[i] = this.code[i] || '';
    }

    if (this.code.length === 6) {
      this.confirm();
    }
  }

  confirm(): void {
    if (this.code.length < 6) return;

    this.confirming = true;
    this.errorMessage = '';

    this.http.post<any>(`${environment.apiUrl}/api/admin/auth/totp-setup/confirm/`, {
      totp_code: this.code,
    }).subscribe({
      next: () => {
        this.confirming = false;
        this.successMessage = 'TOTP configuré avec succès !';
        setTimeout(() => this.router.navigate(['/admin']), 1500);
      },
      error: (err) => {
        this.confirming = false;
        this.errorMessage = err.error?.detail || 'Code incorrect ou expiré.';
        this.code = '';
        this.digits = ['', '', '', '', '', ''];
        setTimeout(() => this.focusHiddenInput(), 50);
      },
    });
  }
}
