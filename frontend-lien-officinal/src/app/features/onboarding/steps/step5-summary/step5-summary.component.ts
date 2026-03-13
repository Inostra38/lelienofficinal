import { Component, inject, output, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { OnboardingService } from '../../../../core/services/onboarding.service';

@Component({
  selector: 'app-step5-summary',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './step5-summary.component.html',
})
export class Step5SummaryComponent {
  private onboardingService = inject(OnboardingService);
  private router = inject(Router);

  prev = output<void>();

  saving = signal(false);
  error = signal<string | null>(null);

  get state() {
    return this.onboardingService.state();
  }

  get resourceCount(): number {
    return this.state.classifiedResources.length;
  }

  get collaboratorCount(): number {
    return this.state.collaborators.length;
  }

  onPrev() {
    this.prev.emit();
  }

  onFinish() {
    this.saving.set(true);
    this.error.set(null);

    this.onboardingService.completeWizard().subscribe({
      next: () => {
        this.saving.set(false);
        this.router.navigate(['/dashboard']);
      },
      error: () => {
        this.saving.set(false);
        this.error.set('Une erreur est survenue lors de la sauvegarde.');
      }
    });
  }

  onGoToDashboard() {
    // Accès direct même en cas d'erreur
    this.router.navigate(['/dashboard']);
  }
}
