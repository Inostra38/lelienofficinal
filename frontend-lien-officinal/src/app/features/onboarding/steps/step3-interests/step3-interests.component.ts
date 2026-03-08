import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { OnboardingService, OnboardingCategory } from '../../../../core/services/onboarding.service';
import { switchMap } from 'rxjs/operators';

interface CategoryOption {
  nom: string;
  icon_slug: string;
  selected: boolean;
}

@Component({
  selector: 'app-step3-interests',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './step3-interests.component.html',
})
export class Step3InterestsComponent {
  protected onboarding = inject(OnboardingService);
  private router = inject(Router);

  error = '';
  loading = false;

  categories: CategoryOption[] = [
    { nom: 'Médicaments', icon_slug: 'pill', selected: false },
    { nom: 'Ordonnances', icon_slug: 'file-text', selected: false },
    { nom: 'Homéopathie', icon_slug: 'leaf', selected: false },
    { nom: 'Parapharmacie', icon_slug: 'shopping-bag', selected: false },
    { nom: 'Dermatologie', icon_slug: 'sun', selected: false },
    { nom: 'Pédiatrie', icon_slug: 'baby', selected: false },
    { nom: 'Nutrition', icon_slug: 'apple', selected: false },
    { nom: 'Matériel médical', icon_slug: 'activity', selected: false },
    { nom: 'Vaccination', icon_slug: 'shield', selected: false },
  ];

  toggle(cat: CategoryOption) {
    cat.selected = !cat.selected;
  }

  get selectedCount(): number {
    return this.categories.filter(c => c.selected).length;
  }

  submit() {
    this.error = '';

    if (this.selectedCount === 0) {
      this.error = 'Sélectionnez au moins un centre d\'intérêt.';
      return;
    }

    this.loading = true;
    const selected: OnboardingCategory[] = this.categories
      .filter(c => c.selected)
      .map(c => ({ nom: c.nom, icon_slug: c.icon_slug }));

    this.onboarding.initCategories(selected).pipe(
      switchMap(() => this.onboarding.completeOnboarding())
    ).subscribe({
      next: () => {
        this.loading = false;
        this.router.navigate(['/dashboard']);
      },
      error: () => {
        this.loading = false;
        this.error = 'Une erreur est survenue.';
      }
    });
  }
}
