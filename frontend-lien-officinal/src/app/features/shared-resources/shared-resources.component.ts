import { environment } from '../../../environments/environment';
import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { Subject } from 'rxjs';
import { debounceTime } from 'rxjs/operators';
import { ResourceCard, Category } from '../dashboard/dashboard.component';
import { CategoryAssignerModalComponent } from '../../shared/ui/category-assigner-modal/category-assigner-modal.component';

@Component({
  selector: 'app-shared-resources',
  standalone: true,
  imports: [CommonModule, FormsModule, CategoryAssignerModalComponent],
  templateUrl: './shared-resources.component.html',
})
export class SharedResourcesComponent implements OnInit, OnDestroy {
  private http = inject(HttpClient);
  private router = inject(Router);
  private searchSubject = new Subject<void>();

  resources: ResourceCard[] = [];
  categories: Category[] = [];
  assignedCardIds: Set<number> = new Set();
  searchQuery = '';
  selectedCard: ResourceCard | null = null;
  activeFilter: 'ALL' | 'OFFICIAL' | 'PARTNER' = 'ALL';

  currentPage = 1;
  totalCount = 0;
  pageSize = 20;
  get totalPages(): number { return Math.ceil(this.totalCount / this.pageSize); }

  loadPage(page: number): void {
    this.currentPage = page;
    const params: string[] = [`page=${page}`];
    if (this.searchQuery.trim()) params.push(`search=${encodeURIComponent(this.searchQuery.trim())}`);
    if (this.activeFilter !== 'ALL') params.push(`type=${this.activeFilter}`);

    this.http.get<{ count: number; results: ResourceCard[] }>(
      `${environment.apiUrl}/api/catalog/cards/?${params.join('&')}`
    ).subscribe({
      next: data => { this.resources = data.results; this.totalCount = data.count; },
      error: err => console.error(err)
    });
  }

  onSearchChange(): void {
    this.searchSubject.next();
  }

  ngOnDestroy(): void {
    this.searchSubject.complete();
  }

  onFilterChange(): void {
    this.loadPage(1);
  }

  ngOnInit(): void {
    this.searchSubject.pipe(debounceTime(350)).subscribe(() => this.loadPage(1));
    this.loadPage(1);

    this.http.get<Category[]>(environment.apiUrl + '/api/categories/').subscribe({
      next: data => {
        this.categories = data;
        // Extraire les IDs des cartes déjà adoptées depuis adopted_cards
        const ids = new Set<number>();
        data.forEach(cat => {
          (cat.adopted_cards || []).forEach(card => ids.add(card.id));
        });
        this.assignedCardIds = ids;
      },
      error: err => console.error(err)
    });
  }

  get featuredResources(): ResourceCard[] {
    return this.resources.filter(r => r.is_featured);
  }

  get filteredResources(): ResourceCard[] {
    return this.resources.filter(r => !r.is_featured);
  }

  isAlreadyAdded(card: ResourceCard): boolean {
    return this.assignedCardIds.has(card.id);
  }

  addToBoard(card: ResourceCard): void {
    this.selectedCard = card;
  }

  assignCategory(categoryId: number): void {
    if (!this.selectedCard) return;
    this.http.patch(
      `${environment.apiUrl}/api/cards/${this.selectedCard.id}/assign-category/`,
      { category: categoryId }
    ).subscribe({
      next: () => {
        if (this.selectedCard) {
          this.assignedCardIds.add(this.selectedCard.id);
        }
        this.selectedCard = null;
      },
      error: err => { console.error(err); this.selectedCard = null; }
    });
  }

  goBack(): void {
    this.router.navigate(['/dashboard']);
  }
}
