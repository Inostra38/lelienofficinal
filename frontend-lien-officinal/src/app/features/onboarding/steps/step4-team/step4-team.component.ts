import { Component, inject, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { OnboardingService, WizardCollaborator } from '../../../../core/services/onboarding.service';

const EMPTY_COLLABORATOR = (): WizardCollaborator => ({
  first_name: '',
  last_name: '',
  role: 'Titulaire',
  pin: '',
});

@Component({
  selector: 'app-step4-team',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './step4-team.component.html',
})
export class Step4TeamComponent {
  private onboardingService = inject(OnboardingService);

  next = output<void>();
  prev = output<void>();
  skip = output<void>();

  collaborators: WizardCollaborator[] = [];

  readonly roles = [
    { value: 'Titulaire', label: 'Titulaire' },
    { value: 'Adjoint', label: 'Adjoint' },
    { value: 'Préparateur', label: 'Préparateur' },
    { value: 'Étudiant', label: 'Étudiant' },
    { value: 'Apprenti', label: 'Apprenti' },
  ];

  addCollaborator() {
    this.collaborators = [...this.collaborators, EMPTY_COLLABORATOR()];
  }

  removeCollaborator(index: number) {
    this.collaborators = this.collaborators.filter((_, i) => i !== index);
  }

  isCollaboratorValid(c: WizardCollaborator): boolean {
    return c.first_name.trim().length > 0 && c.last_name.trim().length > 0;
  }

  get allValid(): boolean {
    return this.collaborators.every(c => this.isCollaboratorValid(c));
  }

  onNext() {
    const valid = this.collaborators.filter(c => this.isCollaboratorValid(c));
    this.onboardingService.setCollaborators(valid);
    this.next.emit();
  }

  onPrev() {
    this.prev.emit();
  }

  onSkip() {
    this.onboardingService.setCollaborators([]);
    this.skip.emit();
  }
}
