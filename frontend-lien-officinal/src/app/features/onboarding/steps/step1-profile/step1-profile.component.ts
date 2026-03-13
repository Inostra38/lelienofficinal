import { Component, OnInit, inject, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { OnboardingService } from '../../../../core/services/onboarding.service';

@Component({
  selector: 'app-step1-profile',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './step1-profile.component.html',
})
export class Step1ProfileComponent implements OnInit {
  private http = inject(HttpClient);
  private onboardingService = inject(OnboardingService);

  next = output<void>();

  nomOfficine = '';
  city = '';
  cityReadonly = false;

  ngOnInit() {
    this.http.get<any>('http://127.0.0.1:8000/api/pharmacy/me/').subscribe({
      next: (pharmacy) => {
        this.nomOfficine = pharmacy.nom_officine || '';
        this.city = pharmacy.city || '';
        this.cityReadonly = !!pharmacy.city;
      }
    });
  }

  get isValid(): boolean {
    return this.nomOfficine.trim().length > 0 && this.city.trim().length > 0;
  }

  onNext() {
    if (!this.isValid) return;
    this.onboardingService.setPharmacy({
      nom_officine: this.nomOfficine.trim(),
      city: this.city.trim(),
    });
    this.next.emit();
  }
}
