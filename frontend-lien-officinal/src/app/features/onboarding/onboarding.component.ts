import { Component, inject, signal } from '@angular/core';
import { CommonModule, DecimalPipe } from '@angular/common';
import { OnboardingService } from '../../core/services/onboarding.service';
import { Step1ProfileComponent } from './steps/step1-profile/step1-profile.component';
import { Step2CategoriesComponent } from './steps/step2-categories/step2-categories.component';
import { Step3ResourcesComponent } from './steps/step3-resources/step3-resources.component';
import { Step4TeamComponent } from './steps/step4-team/step4-team.component';
import { Step5SummaryComponent } from './steps/step5-summary/step5-summary.component';

const TOTAL_STEPS = 5;

@Component({
  selector: 'app-onboarding',
  standalone: true,
  imports: [
    CommonModule,
    DecimalPipe,
    Step1ProfileComponent,
    Step2CategoriesComponent,
    Step3ResourcesComponent,
    Step4TeamComponent,
    Step5SummaryComponent,
  ],
  templateUrl: './onboarding.component.html',
})
export class OnboardingComponent {
  onboardingService = inject(OnboardingService);

  currentStep = signal(1);
  readonly totalSteps = TOTAL_STEPS;

  get progressPercent(): number {
    return (this.currentStep() / this.totalSteps) * 100;
  }

  next() {
    if (this.currentStep() < this.totalSteps) {
      this.currentStep.update(s => s + 1);
    }
  }

  prev() {
    if (this.currentStep() > 1) {
      this.currentStep.update(s => s - 1);
    }
  }

  // Skip step4 (équipe) → aller directement au step5
  skipToSummary() {
    this.currentStep.set(this.totalSteps);
  }
}
