import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';

import { PharmacyService } from '../../core/services/pharmacy.service';
import { SmsService } from '../../core/services/sms.service';

@Component({
  selector: 'app-sms-settings',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './sms-settings.component.html',
})
export class SmsSettingsComponent implements OnInit {
  private pharmacyService = inject(PharmacyService);
  private smsService = inject(SmsService);

  smsCredits = 0;
  monthlySmsCount = 0;
  isLoading = true;

  showBuyModal = false;
  emailCopied = false;

  readonly contactEmail = 'sms@lelienofficinal.fr';

  ngOnInit() {
    this.pharmacyService.getCurrentPharmacy().subscribe({
      next: (data) => { this.smsCredits = data.sms_credits ?? 0; }
    });
    this.smsService.getLogs().subscribe({
      next: (logs) => {
        const now = new Date();
        this.monthlySmsCount = logs.filter(l => {
          const d = new Date(l.sent_at);
          return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth();
        }).length;
        this.isLoading = false;
      },
      error: () => { this.isLoading = false; }
    });
  }

  get creditBarWidth(): string {
    const max = 200;
    return Math.min((this.smsCredits / max) * 100, 100) + '%';
  }

  get creditBarColor(): string {
    if (this.smsCredits > 50) return 'bg-green-500';
    if (this.smsCredits > 10) return 'bg-amber-500';
    return 'bg-red-500';
  }

  copyEmail() {
    navigator.clipboard.writeText(this.contactEmail).then(() => {
      this.emailCopied = true;
      setTimeout(() => { this.emailCopied = false; }, 2000);
    });
  }
}
