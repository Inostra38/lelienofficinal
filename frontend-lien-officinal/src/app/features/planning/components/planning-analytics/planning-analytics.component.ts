import {
  Component,
  OnInit,
  AfterViewInit,
  OnDestroy,
  Output,
  EventEmitter,
  inject,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  PlanningService,
  AnalyticsData,
  PayeSummaryResponse,
  PayeCollaborateur,
} from '../../../../core/services/planning.service';

@Component({
  selector: 'app-planning-analytics',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './planning-analytics.component.html',
  styleUrl: './planning-analytics.component.css',
})
export class PlanningAnalyticsComponent implements OnInit, AfterViewInit, OnDestroy {
  @Output() closed = new EventEmitter<void>();

  private planningService = inject(PlanningService);

  // ── Analytics tab ────────────────────────────────────────────────────────────

  period: 'week' | 'month' | 'year' = 'month';
  currentDate = new Date();
  data: AnalyticsData | null = null;
  loading = false;
  error    = false;

  // Chart.js instance (dynamically imported)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private chart: any = null;

  // ── Tab management ───────────────────────────────────────────────────────────

  activeTab: 'analytics' | 'paye' = 'analytics';

  // ── Paye tab ─────────────────────────────────────────────────────────────────

  payeData: PayeSummaryResponse | null = null;
  payeLoading = false;
  payeError = false;
  payeDate = new Date();
  expandedRows = new Set<number>();

  ngOnInit(): void {
    this.load();
  }

  ngAfterViewInit(): void {
    // Chart will be built after data loads
  }

  ngOnDestroy(): void {
    this.destroyChart();
  }

  // ── Tab methods ──────────────────────────────────────────────────────────────

  setTab(tab: 'analytics' | 'paye'): void {
    this.activeTab = tab;
    if (tab === 'paye' && !this.payeData && !this.payeLoading) {
      this.loadPaye();
    }
  }

  // ── Paye methods ─────────────────────────────────────────────────────────────

  loadPaye(): void {
    this.payeLoading = true;
    this.payeError = false;
    this.planningService.getPayeSummary(this.payeMonthStr).subscribe({
      next: (data) => {
        this.payeData = data;
        this.payeLoading = false;
      },
      error: () => {
        this.payeLoading = false;
        this.payeError = true;
      },
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
    if (this.expandedRows.has(id)) {
      this.expandedRows.delete(id);
    } else {
      this.expandedRows.add(id);
    }
  }

  isExpanded(id: number): boolean {
    return this.expandedRows.has(id);
  }

  get payeMonthStr(): string {
    const y = this.payeDate.getFullYear();
    const m = String(this.payeDate.getMonth() + 1).padStart(2, '0');
    return `${y}-${m}`;
  }

  get payeMonthLabel(): string {
    return this.payeDate.toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' });
  }

  formatSolde(h: number): string {
    const sign = h >= 0 ? '+' : '';
    return `${sign}${this.formatH(h)}`;
  }

  contingentWidth(n: number): string {
    const pct = Math.min(100, (n / 150) * 100);
    return `${pct.toFixed(1)}%`;
  }

  rcr_alerte_date(): string {
    const d = new Date();
    d.setMonth(d.getMonth() + 2);
    return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });
  }

  getSalariesCollaborateurs(): PayeCollaborateur[] {
    return this.payeData?.collaborateurs.filter(c => !c.is_tns) ?? [];
  }

  // ── Computed totals ─────────────────────────────────────────────────────────

  get totalHours(): number {
    return this.data?.hours_summary.reduce((a, r) => a + r.total_hours, 0) ?? 0;
  }

  get totalContractHours(): number {
    return this.data?.hours_summary.reduce((a, r) => a + r.contract_hours, 0) ?? 0;
  }

  get totalAbsenceDays(): number {
    if (!this.data?.absences?.by_type) return 0;
    const bt = this.data.absences.by_type;
    return (bt.cp ?? 0) + (bt.maladie ?? 0) + (bt.rcr ?? 0) + (bt.sans_solde ?? 0);
  }

  get coverageRate(): number {
    return this.data?.coverage?.coverage_rate ?? 0;
  }

  get byCollaboratorEntries(): { name: string; cp: number; maladie: number; rcr: number; sans_solde: number }[] {
    if (!this.data?.absences?.by_collaborator) return [];
    return Object.entries(this.data.absences.by_collaborator).map(([name, v]) => ({
      name,
      cp:          v.cp,
      maladie:     v.maladie,
      rcr:         v.rcr,
      sans_solde:  v.sans_solde,
    }));
  }

  // ── Navigation ──────────────────────────────────────────────────────────────

  prevPeriod(): void {
    const d = new Date(this.currentDate);
    if (this.period === 'week') {
      d.setDate(d.getDate() - 7);
    } else if (this.period === 'month') {
      d.setMonth(d.getMonth() - 1);
    } else {
      d.setFullYear(d.getFullYear() - 1);
    }
    this.currentDate = d;
    this.load();
  }

  nextPeriod(): void {
    const d = new Date(this.currentDate);
    if (this.period === 'week') {
      d.setDate(d.getDate() + 7);
    } else if (this.period === 'month') {
      d.setMonth(d.getMonth() + 1);
    } else {
      d.setFullYear(d.getFullYear() + 1);
    }
    this.currentDate = d;
    this.load();
  }

  goToToday(): void {
    this.currentDate = new Date();
    this.load();
  }

  setPeriod(p: 'week' | 'month' | 'year'): void {
    this.period = p;
    this.load();
  }

  // ── Label ───────────────────────────────────────────────────────────────────

  get periodLabel(): string {
    const d = this.currentDate;
    if (this.period === 'week') {
      // Compute Monday of the current week
      const day    = d.getDay();
      const diff   = day === 0 ? -6 : 1 - day;
      const monday = new Date(d);
      monday.setDate(d.getDate() + diff);
      const sunday = new Date(monday);
      sunday.setDate(monday.getDate() + 6);
      const fmt = (dt: Date) => dt.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' });
      return `${fmt(monday)} – ${fmt(sunday)} ${monday.getFullYear()}`;
    }
    if (this.period === 'month') {
      return d.toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' });
    }
    return String(d.getFullYear());
  }

  get dateIso(): string {
    return this.currentDate.toISOString().substring(0, 10);
  }

  // ── Load data ───────────────────────────────────────────────────────────────

  load(): void {
    this.loading = true;
    this.error   = false;
    this.destroyChart();

    this.planningService.getAnalytics(this.period, this.dateIso).subscribe({
      next: (data) => {
        this.data    = data;
        this.loading = false;
        if (this.period === 'year') {
          setTimeout(() => this.buildChart(), 50);
        }
      },
      error: () => {
        this.loading = false;
        this.error   = true;
      },
    });
  }

  // ── Chart (fallback to table if Chart.js not available) ─────────────────────

  buildChart(): void {
    const canvas = document.getElementById('monthlyChart') as HTMLCanvasElement | null;
    if (!canvas || !this.data?.monthly_evolution?.length) return;

    // Try to use Chart.js if available globally
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const ChartConstructor = (window as any)['Chart'];
    if (!ChartConstructor) return;

    this.destroyChart();

    const labels = this.data.monthly_evolution.map(r => r.month_label);
    const hours  = this.data.monthly_evolution.map(r => r.total_hours);
    const absences = this.data.monthly_evolution.map(r => r.absences);

    this.chart = new ChartConstructor(canvas, {
      type: 'bar',
      data: {
        labels,
        datasets: [
          {
            label: 'Heures planifiées',
            data: hours,
            backgroundColor: 'rgba(21, 128, 61, 0.7)',
            borderColor: 'rgba(21, 128, 61, 1)',
            borderWidth: 1,
            borderRadius: 4,
          },
          {
            label: 'Jours d\'absence',
            data: absences,
            backgroundColor: 'rgba(249, 115, 22, 0.6)',
            borderColor: 'rgba(249, 115, 22, 1)',
            borderWidth: 1,
            borderRadius: 4,
            yAxisID: 'y1',
          },
        ],
      },
      options: {
        responsive: true,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { position: 'top' },
        },
        scales: {
          y:  { beginAtZero: true, title: { display: true, text: 'Heures' } },
          y1: {
            beginAtZero: true,
            position: 'right',
            grid: { drawOnChartArea: false },
            title: { display: true, text: 'Jours absence' },
          },
        },
      },
    });
  }

  private destroyChart(): void {
    if (this.chart) {
      this.chart.destroy();
      this.chart = null;
    }
  }

  // ── Helpers ─────────────────────────────────────────────────────────────────

  extraClass(extra: number): string {
    if (extra > 0) return 'text-green-700 font-semibold';
    if (extra < 0) return 'text-red-600 font-semibold';
    return 'text-gray-500';
  }

  formatH(h: number): string {
    const sign  = h < 0 ? '-' : '';
    const abs   = Math.abs(h);
    const hours = Math.floor(abs);
    const mins  = Math.round((abs - hours) * 60);
    return mins > 0 ? `${sign}${hours}h${String(mins).padStart(2, '0')}` : `${sign}${hours}h`;
  }

  get chartAvailable(): boolean {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return !!(window as any)['Chart'];
  }
}
