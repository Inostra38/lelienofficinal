import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { tap } from 'rxjs/operators';
import { AuthService } from '../auth/auth.service';

export interface OnboardingCategory {
  nom: string;
  icon_slug: string;
}

@Injectable({
  providedIn: 'root'
})
export class OnboardingService {
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private baseUrl = 'http://127.0.0.1:8000/api';

  currentStep = signal<number>(1);

  setupProfile(data: { nom_officine: string; city: string; siret?: string }) {
    return this.http.patch(`${this.baseUrl}/auth/profile/setup/`, data);
  }

  initCategories(categories: OnboardingCategory[]) {
    return this.http.post(`${this.baseUrl}/categories/init/`, { categories });
  }

  completeOnboarding() {
    return this.http.post(`${this.baseUrl}/auth/onboarding/complete/`, {}).pipe(
      tap(() => this.authService.setOnboardingCompleted())
    );
  }

  nextStep() {
    this.currentStep.update(s => s + 1);
  }

  prevStep() {
    this.currentStep.update(s => s - 1);
  }
}
