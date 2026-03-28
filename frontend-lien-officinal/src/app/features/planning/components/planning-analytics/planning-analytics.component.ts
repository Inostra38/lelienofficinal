import {
  Component,
  OnInit,
  Output,
  EventEmitter,
  inject,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  PlanningService,
  PayeSummaryResponse,
  PayeCollaborateur,
} from '../../../../core/services/planning.service';
import { resolveColor } from '../../../../core/utils/collaborator-colors';

@Component({
  selector: 'app-planning-analytics',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './planning-analytics.component.html',
  styleUrl: './planning-analytics.component.css',
})
export class PlanningAnalyticsComponent implements OnInit {
  @Output() closed = new EventEmitter<void>();

  private planningService = inject(PlanningService);

  payeData: PayeSummaryResponse | null = null;
  payeLoading = false;
  payeError   = false;
  payeDate    = new Date();
  expandedRows = new Set<number>();

  ngOnInit(): void {
    this.loadPaye();
  }

  loadPaye(): void {
    this.payeLoading = true;
    this.payeError   = false;
    this.planningService.getPayeSummary(this.payeMonthStr).subscribe({
      next: (data) => { this.payeData = data; this.payeLoading = false; },
      error: ()     => { this.payeLoading = false; this.payeError = true; },
    });
  }

  prevPayeMonth(): void {
    const d = new Date(this.payeDate);
    d.setMonth(d.getMonth() - 1);
    this.payeDate = d;
    this.payeData = null;
    this.expandedRows.clear();
    this.loadPaye();
  }

  nextPayeMonth(): void {
    const d = new Date(this.payeDate);
    d.setMonth(d.getMonth() + 1);
    this.payeDate = d;
    this.payeData = null;
    this.expandedRows.clear();
    this.loadPaye();
  }

  toggleRow(id: number): void {
    if (this.expandedRows.has(id)) this.expandedRows.delete(id);
    else this.expandedRows.add(id);
  }

  isExpanded(id: number): boolean { return this.expandedRows.has(id); }

  get payeMonthStr(): string {
    const y = this.payeDate.getFullYear();
    const m = String(this.payeDate.getMonth() + 1).padStart(2, '0');
    return `${y}-${m}`;
  }

  get payeMonthLabel(): string {
    return this.payeDate.toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' });
  }

  getSalariesCollaborateurs(): PayeCollaborateur[] {
    return this.payeData?.collaborateurs.filter(c => !c.is_tns) ?? [];
  }

  getColor(color: string) { return resolveColor(color); }

  formatAlerte10h(jours: { date: string; heures: number }[]): string {
    return 'Journée > 10h : ' + jours.map(j => j.date + ' (' + j.heures + 'h)').join(', ');
  }

  contingentWidth(n: number): string {
    return `${Math.min(100, (n / 150) * 100).toFixed(1)}%`;
  }

  formatH(h: number): string {
    const sign  = h < 0 ? '-' : '';
    const abs   = Math.abs(h);
    const hours = Math.floor(abs);
    const mins  = Math.round((abs - hours) * 60);
    return mins > 0 ? `${sign}${hours}h${String(mins).padStart(2, '0')}` : `${sign}${hours}h`;
  }
}
