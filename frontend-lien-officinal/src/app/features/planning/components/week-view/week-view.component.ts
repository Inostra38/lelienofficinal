import { Component, Input, Output, EventEmitter, inject, OnChanges, SimpleChanges, ChangeDetectionStrategy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CdkDragDrop } from '@angular/cdk/drag-drop';
import {
  PlanningService,
  WeekResponse,
  Shift,
  CollaboratorWeekSummary,
  PharmacyDayStatus,
  OpeningHours,
} from '../../../../core/services/planning.service';
import type { AdjustmentSummary } from '../../../../core/services/planning.service';
import { ShiftFormComponent, ShiftFormCollab } from '../shift-form/shift-form.component';

@Component({
  selector: 'app-week-view',
  standalone: true,
  imports: [CommonModule, ShiftFormComponent],
  templateUrl: './week-view.component.html',
  styleUrl: './week-view.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class WeekViewComponent implements OnChanges {
  @Input() weekData!: WeekResponse;
  @Input() isManager = false;
  @Input() currentWeekStr = '';
  @Input() activeCollaboratorId: number | null = null;
  @Input() openingHours: OpeningHours[] = [];

  @Output() shiftChanged = new EventEmitter<void>();

  private planningService = inject(PlanningService);

  // ── Cache pré-calculé (rebuil dans ngOnChanges) ───────────────────────────

  _weekDaysWithIso: { date: Date; iso: string; label: string }[] = [];
  _hours: number[] = [];
  _shiftsIndex = new Map<string, Shift[]>();
  _summaryByDay = new Map<string, CollaboratorWeekSummary[]>();
  _rowGradients = new Map<number, string>();
  _summaryMap = new Map<number, CollaboratorWeekSummary>();

  ngOnChanges(_changes: SimpleChanges) {
    this._rebuild();
  }

  private _rebuild() {
    if (!this.weekData) return;

    // Jours de la semaine
    const monday = new Date(this.weekData.week_start + 'T00:00:00');
    this._weekDaysWithIso = Array.from({ length: 7 }, (_, i) => {
      const d = new Date(monday);
      d.setDate(monday.getDate() + i);
      const iso = this.getDayIso(d);
      return {
        date: d,
        iso,
        label: d.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }),
      };
    });

    // Index des collaborateurs (O(1) lookup)
    this._summaryMap.clear();
    for (const s of this.weekData.summary) {
      this._summaryMap.set(s.collaborator_id, s);
    }

    // Index des shifts (O(1) lookup par collabId:dayIso)
    this._shiftsIndex.clear();
    for (const shift of this.weekData.shifts) {
      if (!shift.collaborator) continue;
      const key = `${shift.collaborator.id}:${shift.start_datetime.substring(0, 10)}`;
      const list = this._shiftsIndex.get(key);
      if (list) list.push(shift);
      else this._shiftsIndex.set(key, [shift]);
    }

    // Plage horaire
    this._hours = Array.from({ length: this.totalHours + 1 }, (_, i) => this.dayStartHour + i);

    // Gradients CSS (1 par index de jour, pas par collab×jour)
    this._rowGradients.clear();
    for (let i = 0; i < 7; i++) {
      this._rowGradients.set(i, this._computeRowGradient(i));
    }

    // Résumé filtré par jour (contrats)
    const contracts = this.weekData.contracts;
    const visible = this.visibleSummary;
    this._summaryByDay.clear();
    for (const dayObj of this._weekDaysWithIso) {
      if (!contracts) {
        this._summaryByDay.set(dayObj.iso, visible);
      } else {
        this._summaryByDay.set(dayObj.iso, visible.filter(s => {
          const c = contracts[s.collaborator_id];
          if (!c) return true;
          if (dayObj.iso < c.start_date) return false;
          if (c.end_date && dayObj.iso > c.end_date) return false;
          return true;
        }));
      }
    }
  }

  // ── TrackBy ───────────────────────────────────────────────────────────────

  trackByDay = (_: number, d: { date: Date; iso: string }) => d.iso;
  trackByCollabId = (_: number, s: CollaboratorWeekSummary) => s.collaborator_id;
  trackByShiftId = (_: number, s: Shift) => s.id;
  trackByHour = (_: number, h: number) => h;
  trackByAdjId = (_: number, a: AdjustmentSummary) => a.adjustment_id;

  // ── Shift form ────────────────────────────────────────────────────────────
  showShiftForm             = false;
  shiftFormCollaboratorId: number | null = null;
  shiftFormDate             = '';

  openShiftForm(collaboratorId: number, dayIso: string) {
    this.shiftFormCollaboratorId = collaboratorId;
    this.shiftFormDate           = dayIso;
    this.showShiftForm           = true;
  }

  onShiftCreated() {
    this.showShiftForm = false;
    this.shiftChanged.emit();
  }

  get shiftFormCollaborators(): ShiftFormCollab[] {
    return this.weekData.summary.map(s => ({
      id:        s.collaborator_id,
      full_name: s.full_name,
      color:     s.color,
    }));
  }

  // ── Vue filtrée (staff voit uniquement sa ligne, ou toute l'équipe) ─────────

  @Input() showFullTeam = false;
  @Input() filteredCollaboratorIds: number[] | null = null;

  get visibleSummary(): CollaboratorWeekSummary[] {
    let base: CollaboratorWeekSummary[];
    if (this.isManager) {
      base = this.weekData.summary;
    } else if (this.activeCollaboratorId == null) {
      return [];
    } else if (this.showFullTeam) {
      base = this.weekData.summary;
    } else {
      base = this.weekData.summary.filter(s => s.collaborator_id === this.activeCollaboratorId);
    }
    if (this.filteredCollaboratorIds !== null && this.filteredCollaboratorIds.length > 0) {
      return base.filter(s => this.filteredCollaboratorIds!.includes(s.collaborator_id));
    }
    return base;
  }

  // ── Filtrage par contrat ──────────────────────────────────────────────────

  /** Lookup O(1) depuis le cache pré-calculé */
  getVisibleSummaryForDay(dayIso: string): CollaboratorWeekSummary[] {
    return this._summaryByDay.get(dayIso) ?? this.visibleSummary;
  }

  // ── Jours de la semaine ────────────────────────────────────────────────────

  get printWeekLabel(): string {
    const monday = new Date(this.weekData.week_start + 'T00:00:00');
    const sunday = new Date(monday.getTime() + 6 * 86400000);
    const fmt = (d: Date) => d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' });
    const fmtD = (d: Date) => d.toLocaleDateString('fr-FR', { day: 'numeric' });
    const sameMonth = monday.getMonth() === sunday.getMonth();
    return sameMonth
      ? `${fmtD(monday)} – ${fmt(sunday)} ${monday.getFullYear()}`
      : `${fmt(monday)} – ${fmt(sunday)} ${monday.getFullYear()}`;
  }

  get printWeekNumber(): number {
    const monday = new Date(this.weekData.week_start + 'T00:00:00');
    const d = new Date(Date.UTC(monday.getFullYear(), monday.getMonth(), monday.getDate()));
    d.setUTCDate(d.getUTCDate() + 4 - (d.getUTCDay() || 7));
    const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
    return Math.ceil((((d.getTime() - yearStart.getTime()) / 86400000) + 1) / 7);
  }

  get weekDays(): Date[] {
    const monday = new Date(this.weekData.week_start + 'T00:00:00');
    return Array.from({ length: 7 }, (_, i) => {
      const d = new Date(monday);
      d.setDate(monday.getDate() + i);
      return d;
    });
  }

  getDayLabel(d: Date): string {
    return d.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  }

  getDayIso(d: Date): string {
    // toISOString() est UTC et peut décaler la date — on utilise la date locale
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  }

  isToday(d: Date): boolean {
    return d.toDateString() === new Date().toDateString();
  }

  // ── Statuts journaliers ────────────────────────────────────────────────────

  getDayStatus(iso: string): PharmacyDayStatus | null {
    return this.weekData.day_statuses.find(s => s.date === iso) ?? null;
  }

  getDayStatusClasses(iso: string): string {
    const s = this.getDayStatus(iso);
    if (!s) return '';
    if (s.status === 'closed' && !s.on_call_day && !s.on_call_night) return 'bg-red-50 border-red-200';
    if (s.on_call_day || s.on_call_night) return 'bg-amber-50 border-amber-200';
    return '';
  }

  getDayHeaderClasses(iso: string): string {
    const s = this.getDayStatus(iso);
    if (!s) return 'bg-gray-50';
    if (s.status === 'closed' && !s.on_call_day && !s.on_call_night) return 'bg-red-100';
    if (s.on_call_day || s.on_call_night) return 'bg-amber-100';
    return 'bg-gray-50';
  }

  getDayStatusBadge(iso: string): string | null {
    const s = this.getDayStatus(iso);
    if (!s) return null;
    if (s.status === 'closed' && !s.on_call_day && !s.on_call_night) return 'Fermé';
    const parts: string[] = [];
    if (s.on_call_day)   parts.push('Garde J');
    if (s.on_call_night) parts.push('Garde N');
    return parts.length ? parts.join(' · ') : null;
  }

  // ── Shifts ────────────────────────────────────────────────────────────────

  getShiftsForCell(collaboratorId: number, dayIso: string): Shift[] {
    return this.weekData.shifts.filter(s =>
      s.collaborator?.id === collaboratorId &&
      s.start_datetime.startsWith(dayIso)
    );
  }

  // ── Résumé collaborateur ──────────────────────────────────────────────────

  getSummary(collaboratorId: number): CollaboratorWeekSummary | null {
    return this._summaryMap.get(collaboratorId) ?? null;
  }

  getBalanceClass(balance: number): string {
    if (balance > 0) return 'text-orange-600';
    if (balance < 0) return 'text-blue-600';
    return 'text-green-700';
  }

  formatBalance(balance: number): string {
    const sign = balance > 0 ? '+' : '';
    return `${sign}${balance.toFixed(1)}h`;
  }

  // ── Actions manager ───────────────────────────────────────────────────────

  deleteShift(shiftId: number) {
    if (!confirm('Supprimer ce shift ?')) return;
    this.planningService.deleteShift(shiftId).subscribe(() => this.shiftChanged.emit());
  }

  publishShift(shiftId: number) {
    this.planningService.publishShift(shiftId).subscribe(() => this.shiftChanged.emit());
  }

  // ── Drag & drop ───────────────────────────────────────────────────────────

  onDrop(event: CdkDragDrop<string>) {
    if (event.previousContainer === event.container) return;

    const shift: Shift = event.item.data;
    const targetDayIso: string = event.container.data;

    // Même heure, nouvelle date
    const oldStart = new Date(shift.start_datetime);
    const oldEnd   = new Date(shift.end_datetime);
    const duration = oldEnd.getTime() - oldStart.getTime();

    const [year, month, day] = targetDayIso.split('-').map(Number);
    const newStart = new Date(oldStart);
    newStart.setFullYear(year, month - 1, day);
    const newEnd = new Date(newStart.getTime() + duration);

    const fmt = (d: Date) => {
      const p = (n: number) => String(n).padStart(2, '0');
      return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:00`;
    };

    this.planningService.updateShift(shift.id, {
      start_datetime: fmt(newStart),
      end_datetime:   fmt(newEnd),
    }).subscribe(() => this.shiftChanged.emit());
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  getBgClass(color: string): string {
    return `bg-${color}-500`;
  }

  getInitials(summary: CollaboratorWeekSummary): string {
    const parts = summary.full_name.split(' ');
    return parts.map(p => p.charAt(0)).join('').substring(0, 2).toUpperCase();
  }

  getCollaboratorColor(collaboratorId: number): string {
    const shift = this.weekData.shifts.find(s => s.collaborator?.id === collaboratorId);
    if (shift) return shift.collaborator?.color ?? 'gray';
    return this.weekData.summary.find(s => s.collaborator_id === collaboratorId)?.color ?? 'gray';
  }

  // ── Totaux (pied de grille) ───────────────────────────────────────────────

  /** Heures travaillées ce jour pour tous les collaborateurs visibles */
  getDayTotal(dayIso: string): number {
    return this.visibleSummary.reduce((acc, s) => {
      const d = s.days.find(day => day.date === dayIso);
      return acc + (d?.worked_h ?? 0);
    }, 0);
  }

  /** Total planifié toute la semaine pour les collaborateurs visibles */
  get weekTotal(): number {
    return this.visibleSummary.reduce((acc, s) => acc + s.planned_h, 0);
  }

  getAbsenceType(collaboratorId: number, dayIso: string): string | null {
    const summary = this.getSummary(collaboratorId);
    if (!summary) return null;
    const labels: Record<string, string> = {
      cp: 'Congés payés', maladie: 'Maladie', rcr: 'RCR', sans_solde: 'Sans solde',
    };
    // Absence approuvée (via day_summary du backend)
    const day = summary.days.find(d => d.date === dayIso);
    if (day?.absence_type) return labels[day.absence_type] ?? day.absence_type;
    // Absence en attente (non incluse dans day_summary — on la lit directement)
    const pending = summary.absences.find(a =>
      a.status === 'pending' && a.start_date <= dayIso && a.end_date >= dayIso
    );
    return pending ? (labels[pending.type] ?? pending.type) : null;
  }

  getAbsenceStatus(collaboratorId: number, dayIso: string): 'pending' | 'approved' | 'rejected' | null {
    const summary = this.getSummary(collaboratorId);
    if (!summary) return null;
    const absence = summary.absences.find(a =>
      a.start_date <= dayIso && a.end_date >= dayIso
    );
    return absence?.status ?? null;
  }

  // ── Timeline — couleurs collaborateurs ────────────────────────────────────

  private readonly colorPalette: Record<string, { base: string; light: string; text: string }> = {
    green:  { base: '#15803d', light: '#dcfce7', text: '#14532d' },
    blue:   { base: '#1d4ed8', light: '#dbeafe', text: '#1e3a8a' },
    purple: { base: '#7c3aed', light: '#ede9fe', text: '#4c1d95' },
    red:    { base: '#b91c1c', light: '#fee2e2', text: '#7f1d1d' },
    orange: { base: '#c2410c', light: '#ffedd5', text: '#7c2d12' },
    yellow: { base: '#a16207', light: '#fef9c3', text: '#713f12' },
    pink:   { base: '#be185d', light: '#fce7f3', text: '#831843' },
    indigo: { base: '#4338ca', light: '#e0e7ff', text: '#312e81' },
    teal:   { base: '#0f766e', light: '#ccfbf1', text: '#134e4a' },
    cyan:   { base: '#0e7490', light: '#cffafe', text: '#164e63' },
    gray:   { base: '#4b5563', light: '#f3f4f6', text: '#1f2937' },
  };

  getShiftBg(color: string, published: boolean): string {
    const c = this.colorPalette[color] ?? this.colorPalette['gray'];
    return published ? c.base : c.light;
  }

  getShiftText(color: string, published: boolean): string {
    const c = this.colorPalette[color] ?? this.colorPalette['gray'];
    return published ? '#ffffff' : c.text;
  }

  getShiftBorderColor(color: string): string {
    return (this.colorPalette[color] ?? this.colorPalette['gray']).base;
  }

  // ── Timeline ──────────────────────────────────────────────────────────────

  @Input() timelineMode: '24h' | 'zoom' = '24h';

  /** Heure de début de la fenêtre zoom (1h avant la première ouverture) */
  private get zoomStart(): number {
    if (this.openingHours.length === 0) return 8;
    const minMins = Math.min(...this.openingHours.map(h => this._timeToMins(h.start_time)));
    return Math.max(0, Math.floor(minMins / 60) - 1);
  }

  /** Heure de fin de la fenêtre zoom (1h après la dernière fermeture) */
  private get zoomEnd(): number {
    if (this.openingHours.length === 0) return 20;
    const maxMins = Math.max(...this.openingHours.map(h => this._timeToMins(h.end_time)));
    return Math.min(24, Math.ceil(maxMins / 60) + 1);
  }

  get dayStartHour(): number { return this.timelineMode === 'zoom' ? this.zoomStart : 0; }
  get dayEndHour():   number { return this.timelineMode === 'zoom' ? this.zoomEnd   : 24; }
  get totalHours():   number { return this.dayEndHour - this.dayStartHour; }

  /** Lecture du cache — O(1) */
  getRowGradient(dayOfWeek: number): string {
    return this._rowGradients.get(dayOfWeek) ?? '#eef2ff';
  }

  /** Calcul effectif du gradient (appelé uniquement par _rebuild) */
  private _computeRowGradient(dayOfWeek: number): string {
    if (dayOfWeek === 6) return '#eef2ff';

    const slots = this.openingHours
      .filter(h => h.day_of_week === dayOfWeek)
      .map(h => ({ start: this._timeToMins(h.start_time), end: this._timeToMins(h.end_time) }))
      .sort((a, b) => a.start - b.start);

    if (slots.length === 0) return '#eef2ff';

    const viewStart = this.dayStartHour * 60;
    const viewEnd   = this.dayEndHour   * 60;
    const viewTotal = viewEnd - viewStart;
    const pct = (mins: number) => (((mins - viewStart) / viewTotal) * 100).toFixed(3);

    const stops: string[] = [];
    let cur = viewStart;

    for (const { start, end } of slots) {
      const s = Math.max(start, viewStart);
      const e = Math.min(end,   viewEnd);
      if (s >= viewEnd || e <= viewStart) continue;
      if (s > cur) stops.push(`#eef2ff ${pct(cur)}%, #eef2ff ${pct(s)}%`);
      stops.push(`#ffffff ${pct(s)}%, #ffffff ${pct(e)}%`);
      cur = e;
    }
    if (cur < viewEnd) stops.push(`#eef2ff ${pct(cur)}%, #eef2ff 100%`);

    return stops.length ? `linear-gradient(to right, ${stops.join(', ')})` : '#eef2ff';
  }

  private _timeToMins(timeStr: string): number {
    const [h, m] = timeStr.split(':').map(Number);
    return h * 60 + m;
  }

  /** Heures affichées sur la règle */
  get hours(): number[] {
    return Array.from({ length: this.totalHours + 1 }, (_, i) => this.dayStartHour + i);
  }

  getHourLeft(hour: number): number {
    return ((hour - this.dayStartHour) / this.totalHours) * 100;
  }

  getShiftLeft(shift: Shift): number {
    const start = new Date(shift.start_datetime);
    const minutes = (start.getHours() - this.dayStartHour) * 60 + start.getMinutes();
    return Math.max(0, (minutes / (this.totalHours * 60)) * 100);
  }

  getShiftWidth(shift: Shift): number {
    const start    = new Date(shift.start_datetime);
    const end      = new Date(shift.end_datetime);
    const duration = (end.getTime() - start.getTime()) / 60000;
    return Math.min(100 - this.getShiftLeft(shift), (duration / (this.totalHours * 60)) * 100);
  }

  getShiftsForCollabDay(collabId: number, dayIso: string): Shift[] {
    const all = this._shiftsIndex.get(`${collabId}:${dayIso}`) ?? [];
    return this.isManager ? all : all.filter(s => s.is_published);
  }

  formatTime(isoStr: string): string {
    return isoStr.substring(11, 16);
  }

  isClosed(day: Date): boolean {
    return this.getDayStatus(this.getDayIso(day))?.status === 'closed';
  }

  isOnCall(day: Date): boolean {
    const s = this.getDayStatus(this.getDayIso(day));
    return !!(s?.on_call_day || s?.on_call_night);
  }

  getDayBadges(day: Date): { label: string; cls: string }[] {
    const s = this.getDayStatus(this.getDayIso(day));
    if (!s) return [];
    const badges: { label: string; cls: string }[] = [];
    if (s.on_call_day)   badges.push({ label: 'Garde de jour',  cls: 'badge-oncall-day' });
    if (s.on_call_night) badges.push({ label: 'Garde de nuit',  cls: 'badge-oncall-night' });
    if (s.status === 'closed' && !s.on_call_day && !s.on_call_night)
      badges.push({ label: 'Fermé', cls: 'badge-closed' });
    return badges;
  }

  getShortName(summary: CollaboratorWeekSummary): string {
    const parts = summary.full_name.trim().split(/\s+/);
    if (parts.length === 1) return parts[0];
    return `${parts[0]} ${parts[parts.length - 1].charAt(0)}.`;
  }

  onShiftClick(shift: Shift): void {
    if (!this.isManager) return;
    this.shiftFormCollaboratorId = shift.collaborator?.id ?? null;
    this.shiftFormDate           = shift.start_datetime.substring(0, 10);
    this.showShiftForm           = true;
  }

  // ── Ajustements horaires ──────────────────────────────────────────────────

  getAdjustmentsForDay(collaboratorId: number, dayIso: string): AdjustmentSummary[] {
    const summary = this.getSummary(collaboratorId);
    if (!summary) return [];
    return summary.adjustments?.filter(a => a.date === dayIso) ?? [];
  }

  formatDuration(minutes: number): string {
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    if (h > 0 && m > 0) return `${h}h${String(m).padStart(2, '0')}`;
    if (h > 0) return `${h}h`;
    return `${m}min`;
  }

  // ── Popover ajustement ────────────────────────────────────────────────────

  activeAdjPopover: { adj: AdjustmentSummary; x: number; y: number } | null = null;

  onAdjBadgeClick(adj: AdjustmentSummary, event: MouseEvent) {
    event.stopPropagation();
    if (this.activeAdjPopover?.adj.adjustment_id === adj.adjustment_id) {
      this.activeAdjPopover = null;
      return;
    }
    const popoverWidth = 210;
    const x = event.clientX + popoverWidth > window.innerWidth
      ? event.clientX - popoverWidth
      : event.clientX;
    this.activeAdjPopover = { adj, x, y: event.clientY };
  }

  closeAdjPopover() {
    this.activeAdjPopover = null;
  }
}
