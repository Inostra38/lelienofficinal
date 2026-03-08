import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { OnboardingService } from '../../core/services/onboarding.service';
import { Step1AccountComponent } from './steps/step1-account/step1-account.component';
import { Step2OfficineComponent } from './steps/step2-officine/step2-officine.component';
import { Step3InterestsComponent } from './steps/step3-interests/step3-interests.component';
@Component({
  selector: 'app-onboarding',
  standalone: true,
  imports: [
    CommonModule,
    Step1AccountComponent,
    Step2OfficineComponent,
    Step3InterestsComponent,
  ],
  templateUrl: './onboarding.component.html',
})
export class OnboardingComponent {
  onboarding = inject(OnboardingService);
}
