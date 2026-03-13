import { Component, OnInit, inject, output, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { OnboardingService, WizardResource, ClassifiedResource } from '../../../../core/services/onboarding.service';

@Component({
  selector: 'app-step3-resources',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './step3-resources.component.html',
  styleUrls: ['./step3-resources.component.css'],
})
export class Step3ResourcesComponent implements OnInit {
  private onboardingService = inject(OnboardingService);

  next = output<void>();
  prev = output<void>();

  allResources: WizardResource[] = [];
  filteredResources: WizardResource[] = [];
  selectedIds: Set<number> = new Set();
  loading = true;

  // État classification IA
  classifying = signal(false);
  classifyDone = signal(false);
  classifyResult = signal<ClassifiedResource[]>([]);
  classifySummary = signal<{ category: string; count: number }[]>([]);
  uncategorizedCount = signal(0);

  ngOnInit() {
    // Restaurer la sélection précédente
    const previous = this.onboardingService.state().selectedResources;
    this.selectedIds = new Set(previous.map(r => r.id));

    const classified = this.onboardingService.state().classifiedResources;
    if (classified.length > 0) {
      this.classifyDone.set(true);
      this.classifyResult.set(classified);
      this._buildSummary(classified);
    }

    this.onboardingService.getWizardResources().subscribe({
      next: (resources) => {
        this.allResources = resources;
        this.filteredResources = [...resources];
        this.loading = false;
      },
      error: () => { this.loading = false; }
    });
  }

  onSearch(term: string): void {
    const q = term.trim().toLowerCase();
    this.filteredResources = q
      ? this.allResources.filter(r =>
          r.titre.toLowerCase().includes(q) ||
          r.description_officielle.toLowerCase().includes(q)
        )
      : [...this.allResources];
  }

  toggleResource(resource: WizardResource) {
    if (this.selectedIds.has(resource.id)) {
      this.selectedIds.delete(resource.id);
    } else {
      this.selectedIds.add(resource.id);
    }
    this.selectedIds = new Set(this.selectedIds);

    // Relancer la classification si on change la sélection
    if (this.classifyDone()) {
      this.classifyDone.set(false);
      this.classifyResult.set([]);
      this.onboardingService.setClassifiedResources([]);
    }
  }

  isSelected(id: number): boolean {
    return this.selectedIds.has(id);
  }

  get selectedCount(): number {
    return this.selectedIds.size;
  }

  get selectedResources(): WizardResource[] {
    return this.allResources.filter(r => this.selectedIds.has(r.id));
  }

  get allVisibleSelected(): boolean {
    return this.filteredResources.length > 0 &&
      this.filteredResources.every(r => this.selectedIds.has(r.id));
  }

  toggleSelectAll(): void {
    if (this.allVisibleSelected) {
      this.filteredResources.forEach(r => this.selectedIds.delete(r.id));
    } else {
      this.filteredResources.forEach(r => this.selectedIds.add(r.id));
    }
    this.selectedIds = new Set(this.selectedIds);
    if (this.classifyDone()) {
      this.classifyDone.set(false);
      this.classifyResult.set([]);
      this.onboardingService.setClassifiedResources([]);
    }
  }

  truncate(text: string, max = 80): string {
    return text.length > max ? text.slice(0, max) + '…' : text;
  }

  typeBadgeClass(type: string): string {
    switch (type) {
      case 'OFFICIAL': return 'badge-official';
      case 'PARTNER': return 'badge-partner';
      default: return 'badge-private';
    }
  }

  typeBadgeLabel(type: string): string {
    switch (type) {
      case 'OFFICIAL': return 'Officiel';
      case 'PARTNER': return 'Partenaire';
      default: return 'Privé';
    }
  }

  launchClassification() {
    if (this.selectedIds.size === 0) {
      // Pas de ressources sélectionnées — on passe directement
      this.onboardingService.setSelectedResources([]);
      this.onboardingService.setClassifiedResources([]);
      this.next.emit();
      return;
    }

    this.classifying.set(true);
    const categories = this.onboardingService.state().selectedCategories;
    const resources = this.selectedResources;

    this.onboardingService.classifyResources(categories, resources).subscribe({
      next: (result) => {
        this.classifyResult.set(result);
        this._buildSummary(result);
        this.classifyDone.set(true);
        this.classifying.set(false);
        this.onboardingService.setSelectedResources(resources);
        this.onboardingService.setClassifiedResources(result);
      },
      error: () => {
        // Fallback : tout dans "Autre"
        const fallback = resources.map(r => ({ resource_id: r.id, category: 'Autre' }));
        this.classifyResult.set(fallback);
        this._buildSummary(fallback);
        this.classifyDone.set(true);
        this.classifying.set(false);
        this.onboardingService.setSelectedResources(resources);
        this.onboardingService.setClassifiedResources(fallback);
      }
    });
  }

  private _buildSummary(classified: ClassifiedResource[]) {
    const counts: Record<string, number> = {};
    let uncategorized = 0;
    for (const item of classified) {
      if (item.category === 'Autre') {
        uncategorized++;
      } else {
        counts[item.category] = (counts[item.category] || 0) + 1;
      }
    }
    this.classifySummary.set(
      Object.entries(counts).map(([category, count]) => ({ category, count }))
    );
    this.uncategorizedCount.set(uncategorized);
  }

  onNext() {
    if (this.selectedIds.size > 0 && !this.classifyDone()) {
      this.launchClassification();
      return;
    }
    this.onboardingService.setSelectedResources(this.selectedResources);
    this.next.emit();
  }

  onPrev() {
    this.prev.emit();
  }
}
