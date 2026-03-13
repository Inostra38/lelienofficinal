import { Component, OnInit, inject, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { OnboardingService, WizardCategory } from '../../../../core/services/onboarding.service';

const MIN_SELECTION = 1;

@Component({
  selector: 'app-step2-categories',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './step2-categories.component.html',
})
export class Step2CategoriesComponent implements OnInit {
  private onboardingService = inject(OnboardingService);

  next = output<void>();
  prev = output<void>();

  categories: WizardCategory[] = [];
  selected: Set<string> = new Set();
  loading = true;

  readonly MIN = MIN_SELECTION;

  ngOnInit() {
    // Restaurer la sélection précédente si on revient en arrière
    const previous = this.onboardingService.state().selectedCategories;
    this.selected = new Set(previous);

    this.onboardingService.getWizardCategories().subscribe({
      next: (cats) => {
        this.categories = cats;
        this.loading = false;
      },
      error: () => { this.loading = false; }
    });
  }

  toggle(nom: string) {
    if (this.selected.has(nom)) {
      this.selected.delete(nom);
    } else {
      this.selected.add(nom);
    }
    this.selected = new Set(this.selected);
  }

  isSelected(nom: string): boolean {
    return this.selected.has(nom);
  }

  get isValid(): boolean {
    return this.selected.size >= this.MIN;
  }

  onNext() {
    if (!this.isValid) return;
    this.onboardingService.setSelectedCategories(Array.from(this.selected));
    this.next.emit();
  }

  onPrev() {
    this.prev.emit();
  }
}
