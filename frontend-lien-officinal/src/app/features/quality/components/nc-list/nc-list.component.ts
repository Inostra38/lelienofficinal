import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { QualityNcService } from '../../services/quality-nc.service';
import { NonConformity } from '../../models/nonconformity.model';

@Component({
  selector: 'app-nc-list',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './nc-list.component.html',
})
export class NcListComponent implements OnInit {
  private ncService = inject(QualityNcService);

  ncs: NonConformity[] = [];
  loading = true;
  statusFilter = '';
  severityFilter = '';

  readonly statusFilters = [
    { value: '', label: 'Tous' },
    { value: 'open', label: 'Ouvert' },
    { value: 'in_progress', label: 'En cours' },
    { value: 'closed', label: 'Clôturé' },
  ];

  readonly severityFilters = [
    { value: '', label: 'Tous' },
    { value: 'minor', label: 'Mineur' },
    { value: 'major', label: 'Majeur' },
    { value: 'critical', label: 'Critique' },
  ];

  ngOnInit() { this.load(); }

  load() {
    this.loading = true;
    this.ncService.getNonConformities({
      status: this.statusFilter || undefined,
      severity: this.severityFilter || undefined,
    }).subscribe({
      next: (data) => { this.ncs = data; this.loading = false; },
      error: () => { this.loading = false; },
    });
  }

  applyStatusFilter(v: string) { this.statusFilter = v; this.load(); }
  applySeverityFilter(v: string) { this.severityFilter = v; this.load(); }

  get hasActiveFilters(): boolean {
    return this.statusFilter !== '' || this.severityFilter !== '';
  }

  severityClass(s: string): string {
    return ({
      minor: 'bg-blue-50 text-blue-700 border border-blue-200',
      major: 'bg-amber-50 text-amber-700 border border-amber-200',
      critical: 'bg-red-50 text-red-700 border border-red-200',
    } as Record<string, string>)[s] || '';
  }

  severityLabel(s: string): string {
    return ({ minor: 'Mineur', major: 'Majeur', critical: 'Critique' } as Record<string, string>)[s] || s;
  }

  statusLabel(s: string): string {
    return ({ open: 'Ouvert', in_progress: 'En cours', closed: 'Clôturé' } as Record<string, string>)[s] || s;
  }

  statusClass(s: string): string {
    return ({
      open: 'bg-orange-50 text-orange-700 border border-orange-200',
      in_progress: 'bg-blue-50 text-blue-700 border border-blue-200',
      closed: 'bg-gray-50 text-gray-500 border border-gray-200',
    } as Record<string, string>)[s] || '';
  }

  trackById(_: number, nc: NonConformity) { return nc.id; }
}
