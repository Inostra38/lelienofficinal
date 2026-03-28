import { Component, Input, Output, EventEmitter, inject, OnChanges, SimpleChanges, ChangeDetectionStrategy, ChangeDetectorRef } from '@angular/core';
import { resolveColor } from '../../../../core/utils/collaborator-colors';
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
import { ConfirmService } from '../../../../core/services/confirm.service';
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

  @Output() shiftChanged  = new EventEmitter<void>();
  @Output() shiftClicked  = new EventEmitter<Shift>();
  @Output() cellClicked   = new EventEmitter<{ collaboratorId: number; date: string }>();

  private planningService = inject(PlanningService);
  private cdr             = inject(ChangeDetectorRef);
  private confirmService  = inject(ConfirmService);

  // ── Cache pré-calculé (rebuil dans ngOnChanges) ───────────────────────────

  _weekDaysWithIso: { date: Date; iso: string; label: string }[] = [];
  _weekDays: Date[] = [];
  _hours: number[] = [];
  _shiftsIndex = new Map<string, Shift[]>();
  _summaryByDay = new Map<string, CollaboratorWeekSummary[]>();
  _rowGradients = new Map<number, string>();
  _summaryMap = new Map<number, CollaboratorWeekSummary>();
  _shiftFormCollaborators: ShiftFormCollab[] = [];

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
    this._weekDays = this._weekDaysWithIso.map(d => d.date);

    // Collaborateurs pour le formulaire de shift (stable — évite NG0103)
    this._shiftFormCollaborators = this.weekData.summary.map(s => ({
      id:        s.collaborator_id,
      full_name: s.full_name,
      color:     s.color,
    }));

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
      const dayIso = this._weekDaysWithIso[i]?.iso ?? '';
      this._rowGradients.set(i, this._computeRowGradient(i, dayIso));
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
    // Délègue au drawer dans le composant parent
    this.cellClicked.emit({ collaboratorId, date: dayIso });
  }

  onShiftCreated() {
    this.showShiftForm = false;
    this.shiftChanged.emit();
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

  async deleteShift(shiftId: number) {
    if (!await this.confirmService.ask({ title: 'Supprimer le shift', message: 'Supprimer ce shift ?', danger: true })) return;
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


  // ── Timeline — couleurs collaborateurs ────────────────────────────────────

  getShiftBg(color: string, published: boolean, absent = false): string {
    const c    = resolveColor(color);
    const base = published ? c.base : c.light;
    if (!absent) return base;
    const stripe = published ? 'rgba(255,255,255,0.28)' : 'rgba(0,0,0,0.10)';
    return `repeating-linear-gradient(135deg, transparent, transparent 5px, ${stripe} 5px, ${stripe} 9px), ${base}`;
  }

  getShiftText(color: string, published: boolean): string {
    return published ? '#ffffff' : resolveColor(color).text;
  }

  getShiftBorderColor(color: string): string {
    return resolveColor(color).base;
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

  /** Gradient de base ouverture/fermeture (toujours une linear-gradient) */
  private _computeBaseGradient(dayOfWeek: number): string {
    const closed = 'linear-gradient(to right, #eef2ff, #eef2ff)';
    if (dayOfWeek === 6) return closed;

    const slots = this.openingHours
      .filter(h => h.day_of_week === dayOfWeek)
      .map(h => ({ start: this._timeToMins(h.start_time), end: this._timeToMins(h.end_time) }))
      .sort((a, b) => a.start - b.start);

    if (slots.length === 0) return closed;

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

    return stops.length ? `linear-gradient(to right, ${stops.join(', ')})` : closed;
  }

  /** Overlay semi-transparent pour une plage de garde (transparent en dehors) */
  private _buildOnCallOverlay(startMins: number, endMins: number, color: string): string {
    const viewStart  = this.dayStartHour * 60;
    const viewEnd    = this.dayEndHour   * 60;
    const viewTotal  = viewEnd - viewStart;
    const pct = (m: number) =>
      (Math.max(0, Math.min(100, ((m - viewStart) / viewTotal) * 100))).toFixed(3);

    const s = Math.max(startMins, viewStart);
    const e = Math.min(endMins,   viewEnd);
    if (s >= e) return 'linear-gradient(to right, transparent, transparent)';

    const stops: string[] = [];
    if (s > viewStart) stops.push(`transparent ${pct(viewStart)}%, transparent ${pct(s)}%`);
    stops.push(`${color} ${pct(s)}%, ${color} ${pct(e)}%`);
    if (e < viewEnd)   stops.push(`transparent ${pct(e)}%, transparent 100%`);

    return `linear-gradient(to right, ${stops.join(', ')})`;
  }

  /** Calcul effectif du gradient (appelé uniquement par _rebuild) */
  private _computeRowGradient(dayOfWeek: number, dayIso: string): string {
    const base = this._computeBaseGradient(dayOfWeek);
    const wd   = this.weekData;
    const ds   = this.getDayStatus(dayIso);

    const overlays: string[] = [];

    // ── Garde de jour ────────────────────────────────────────────────────────
    const isOnCallDay = ds?.on_call_day ?? (dayOfWeek === 6 && !!wd.on_call_sunday);
    if (isOnCallDay && wd.on_call_day_start && wd.on_call_day_end) {
      overlays.push(this._buildOnCallOverlay(
        this._timeToMins(wd.on_call_day_start),
        this._timeToMins(wd.on_call_day_end),
        'rgba(254, 249, 195, 0.85)',
      ));
    }

    // ── Garde de nuit (avec gestion du franchissement de minuit) ─────────────
    if (wd.on_call_night_start && wd.on_call_night_end) {
      const nightStart      = this._timeToMins(wd.on_call_night_start);
      const nightEnd        = this._timeToMins(wd.on_call_night_end);
      const crossesMidnight = nightEnd < nightStart;
      const color           = 'rgba(186, 230, 253, 0.65)';

      // Ce jour est en garde de nuit
      if (ds?.on_call_night) {
        const endMins = crossesMidnight ? this.dayEndHour * 60 : nightEnd;
        overlays.push(this._buildOnCallOverlay(nightStart, endMins, color));
      }

      // Le jour précédent était en garde de nuit et franchit minuit
      // → la tranche 00h–nightEnd déborde sur ce matin
      if (crossesMidnight) {
        const prevDs = this.getDayStatus(this._prevDayIso(dayIso));
        if (prevDs?.on_call_night) {
          overlays.push(this._buildOnCallOverlay(this.dayStartHour * 60, nightEnd, color));
        }
      }
    }

    // ── Jour férié — overlay plein-jour ambré ─────────────────────────────────
    if (this.getHolidayLabelForIso(dayIso)) {
      overlays.push(this._buildOnCallOverlay(0, 1440, 'rgba(254, 215, 170, 0.45)'));
    }

    return overlays.length ? [...overlays, base].join(', ') : base;
  }

  // ── Jours fériés (calculés côté client, mis en cache par année) ───────────

  private _holidayCache = new Map<number, Map<string, string>>();

  private _computeHolidays(year: number): Map<string, string> {
    if (this._holidayCache.has(year)) return this._holidayCache.get(year)!;
    const a = year % 19, b = Math.floor(year / 100), c = year % 100;
    const d = Math.floor(b / 4), e = b % 4, f = Math.floor((b + 8) / 25);
    const g = Math.floor((b - f + 1) / 3);
    const h = (19 * a + b - d - g + 15) % 30;
    const ii = Math.floor(c / 4), k = c % 4;
    const l = (32 + 2 * e + 2 * ii - h - k) % 7;
    const m = Math.floor((a + 11 * h + 22 * l) / 451);
    const eMonth = Math.floor((h + l - 7 * m + 114) / 31);
    const eDay   = ((h + l - 7 * m + 114) % 31) + 1;
    const easter = new Date(year, eMonth - 1, eDay);
    const shift = (n: number): string => {
      const r = new Date(easter); r.setDate(r.getDate() + n);
      const p = (x: number) => String(x).padStart(2, '0');
      return `${r.getFullYear()}-${p(r.getMonth() + 1)}-${p(r.getDate())}`;
    };
    const holidays = new Map<string, string>([
      [`${year}-01-01`, "Jour de l'An"],
      [shift(1),        'Lundi de Pâques'],
      [`${year}-05-01`, 'Fête du Travail'],
      [`${year}-05-08`, 'Victoire 1945'],
      [shift(39),       'Ascension'],
      [shift(50),       'Lundi de Pentecôte'],
      [`${year}-07-14`, 'Fête Nationale'],
      [`${year}-08-15`, 'Assomption'],
      [`${year}-11-01`, 'Toussaint'],
      [`${year}-11-11`, 'Armistice'],
      [`${year}-12-25`, 'Noël'],
    ]);
    this._holidayCache.set(year, holidays);
    return holidays;
  }

  getHolidayLabelForIso(iso: string): string | null {
    const year = parseInt(iso.substring(0, 4), 10);
    return this._computeHolidays(year).get(iso) ?? null;
  }

  private _prevDayIso(iso: string): string {
    const d = new Date(iso + 'T00:00:00');
    d.setDate(d.getDate() - 1);
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
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
    const s = this.getDayStatus(this.getDayIso(day));
    if (s) return s.status === 'closed' && !s.on_call_day && !s.on_call_night;
    // Dimanche implicitement fermé (sauf si on_call_sunday actif dans les settings)
    if (day.getDay() === 0) return !this.weekData.on_call_sunday;
    return false;
  }

  isOnCall(day: Date): boolean {
    const s = this.getDayStatus(this.getDayIso(day));
    return !!(s?.on_call_day || s?.on_call_night);
  }

  getDayBadges(day: Date): { label: string; cls: string }[] {
    const iso = this.getDayIso(day);
    const badges: { label: string; cls: string }[] = [];

    // Badge Férié (en premier)
    const holidayLabel = this.getHolidayLabelForIso(iso);
    if (holidayLabel) {
      badges.push({ label: holidayLabel, cls: 'badge-ferie' });
    }

    const s = this.getDayStatus(iso);
    if (!s) {
      if (day.getDay() === 0) {
        if (this.weekData.on_call_sunday)
          badges.push({ label: 'Garde de jour', cls: 'badge-oncall-day' });
        else
          badges.push({ label: 'Fermé', cls: 'badge-closed' });
      }
      return badges;
    }
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

  // ── Popover shift ─────────────────────────────────────────────────────────

  activeShiftPopover: { shift: Shift; x: number; y: number } | null = null;
  savingAbsent = false;

  onShiftClick(shift: Shift, event: MouseEvent): void {
    if (!this.isManager) return;
    event.stopPropagation();
    this.shiftClicked.emit(shift);
  }

  closeShiftPopover(): void {
    this.activeShiftPopover = null;
  }

  readonly ABSENCE_TYPES = [
    { value: 'injustifiee',        label: 'Injustifiée' },
    { value: 'conge_exceptionnel', label: 'Congé exceptionnel légal' },
    { value: 'maladie',            label: 'Maladie' },
    { value: 'cp',                 label: 'Congés payés' },
    { value: 'rcr',                label: 'RCR' },
    { value: 'sans_solde',         label: 'Sans solde' },
  ];

  toggleAbsent(shift: Shift): void {
    this.savingAbsent = true;
    const newAbsent = !shift.is_absent;
    const payload: any = { is_absent: newAbsent };
    if (newAbsent) payload.absence_type = shift.absence_type ?? 'injustifiee';
    else payload.absence_type = null;
    this.planningService.updateShift(shift.id, payload).subscribe({
      next: (updated) => {
        this.savingAbsent = false;
        if (this.activeShiftPopover) {
          this.activeShiftPopover = { ...this.activeShiftPopover, shift: updated };
        }
        this.cdr.markForCheck();
        this.shiftChanged.emit();
      },
      error: () => { this.savingAbsent = false; this.cdr.markForCheck(); },
    });
  }

  updateAbsenceType(shift: Shift, type: string): void {
    this.planningService.updateShift(shift.id, { absence_type: type as any }).subscribe({
      next: (updated) => {
        if (this.activeShiftPopover) {
          this.activeShiftPopover = { ...this.activeShiftPopover, shift: updated };
        }
        this.cdr.markForCheck();
        this.shiftChanged.emit();
      },
    });
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
