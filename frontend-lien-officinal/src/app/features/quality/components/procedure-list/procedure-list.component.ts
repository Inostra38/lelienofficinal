import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, Router } from '@angular/router';
import { QualityService } from '../../services/quality.service';
import { Procedure, ProcedureStatus } from '../../models/procedure.model';

@Component({
  selector: 'app-procedure-list',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './procedure-list.component.html',
})
export class ProcedureListComponent implements OnInit {
  private qualityService = inject(QualityService);
  private router = inject(Router);

  tree: Procedure[] = [];
  loading = true;
  error = '';
  statusFilter: ProcedureStatus | 'all' = 'all';
  expandedIds = new Set<number>();

  readonly statusFilters: { value: ProcedureStatus | 'all'; label: string }[] = [
    { value: 'all', label: 'Tous' },
    { value: 'draft', label: 'Brouillon' },
    { value: 'active', label: 'Actif' },
    { value: 'archived', label: 'Archivé' },
  ];

  readonly categoryLabels: Record<string, string> = {
    dispensation: 'Dispensation',
    hygiene: 'Hygiène',
    stock: 'Stock',
    administratif: 'Administratif',
    autre: 'Autre',
  };

  ngOnInit() { this.load(); }

  load() {
    this.loading = true;
    this.qualityService.getProcedureTree().subscribe({
      next: (data) => { this.tree = data; this.loading = false; },
      error: () => { this.error = 'Erreur lors du chargement.'; this.loading = false; },
    });
  }

  get filteredTree(): Procedure[] {
    if (this.statusFilter === 'all') return this.tree;
    return this.tree.filter(p => p.status === this.statusFilter);
  }

  toggleExpand(id: number) {
    if (this.expandedIds.has(id)) this.expandedIds.delete(id);
    else this.expandedIds.add(id);
  }

  isExpanded(id: number): boolean { return this.expandedIds.has(id); }

  statusLabel(s: ProcedureStatus): string {
    return ({ draft: 'Brouillon', active: 'Actif', archived: 'Archivé' } as Record<string, string>)[s] || s;
  }

  statusClass(s: ProcedureStatus): string {
    return ({
      draft: 'bg-amber-50 text-amber-700 border border-amber-200',
      active: 'bg-green-50 text-green-700 border border-green-200',
      archived: 'bg-gray-50 text-gray-500 border border-gray-200',
    } as Record<string, string>)[s] || '';
  }

  publish(p: Procedure, event: Event) {
    event.stopPropagation(); event.preventDefault();
    this.qualityService.publishProcedure(p.id).subscribe({ next: () => this.load() });
  }

  archive(p: Procedure, event: Event) {
    event.stopPropagation(); event.preventDefault();
    if (!confirm(`Archiver "${p.title}" ?`)) return;
    this.qualityService.archiveProcedure(p.id).subscribe({ next: () => this.load() });
  }

  delete(p: Procedure, event: Event) {
    event.stopPropagation(); event.preventDefault();
    if (!confirm(`Supprimer "${p.title}" ?`)) return;
    this.qualityService.deleteProcedure(p.id).subscribe({ next: () => this.load() });
  }

  trackById(_: number, p: Procedure) { return p.id; }
}
