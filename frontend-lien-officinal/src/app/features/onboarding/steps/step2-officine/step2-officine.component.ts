import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { OnboardingService } from '../../../../core/services/onboarding.service';

@Component({
  selector: 'app-step2-officine',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './step2-officine.component.html',
})
export class Step2OfficineComponent {
  protected onboarding = inject(OnboardingService);

  nomOfficine = '';
  city = '';
  siret = '';
  error = '';
  loading = false;

  submit() {
    this.error = '';

    if (!this.nomOfficine.trim()) {
      this.error = "Le nom de l'officine est obligatoire.";
      return;
    }
    if (!this.city.trim()) {
      this.error = 'La ville est obligatoire.';
      return;
    }

    this.loading = true;
    this.onboarding.setupProfile({
      nom_officine: this.nomOfficine,
      city: this.city,
      siret: this.siret || undefined
    }).subscribe({
      next: () => {
        this.loading = false;
        this.onboarding.nextStep();
      },
      error: (err) => {
        this.loading = false;
        const data = err.error;
        if (data?.nom_officine) this.error = data.nom_officine[0];
        else if (data?.city) this.error = data.city[0];
        else this.error = 'Une erreur est survenue.';
      }
    });
  }
}
