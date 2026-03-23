import { Component, Input, Output, EventEmitter, inject, HostListener, OnChanges, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { resolveColor } from '../../../../core/utils/collaborator-colors';
import {
  WeekResponse,
  Shift,
  PharmacyDayStatus,
  PlanningSettings,
  PlanningService,
  MonthlyAbsenceEntry,
  MonthlyAbsenceSummary,
} from '../../../../core/services/planning.service';

export interface MonthDay {
  date: Date;
  iso: string;
  isCurrentMonth: boolean;
  isToday: boolean;
  isPast: boolean;
  shifts: Shift[];
  dayStatus: PharmacyDayStatus | null;
}

@Component({
  selector: 'app-month-view',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './month-view.component.html',
  styleUrl: './month-view.component.css',
})
export class MonthViewComponent implements OnChanges {
  @Input() set weeksData(value: WeekResponse[]) {
    this._weeksData   = value;
    this._allShifts   = value.flatMap(w => w.shifts);
    this._dayStatuses = value.flatMap(w => w.day_statuses);
  }
  @Input() currentMonth!: Date;
  @Input() isManager = false;
  @Input() settings: PlanningSettings | null = null;

  @Output() dayClicked       = new EventEmitter<Date>();
  @Output() dayStatusChanged = new EventEmitter<void>();

  private planningService = inject(PlanningService);

  _weeksData:      WeekResponse[]        = [];
  _allShifts:      Shift[]               = [];
  _dayStatuses:    PharmacyDayStatus[]   = [];
  _absenceSummary: MonthlyAbsenceSummary = {};

  // ── Popup statut ──────────────────────────────────────────────────────────
  popupDay:    MonthDay | null = null;
  savingStatus = false;

  readonly DAY_LABELS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'];

  // ── Jours fériés (calculés côté client, mis en cache par année) ───────────

  private _holidayCache = new Map<number, Map<string, string>>();

  private _computeHolidays(year: number): Map<string, string> {
    if (this._holidayCache.has(year)) return this._holidayCache.get(year)!;

    // Algorithme Meeus/Jones/Butcher pour Pâques
    const a = year % 19;
    const b = Math.floor(year / 100);
    const c = year % 100;
    const d = Math.floor(b / 4);
    const e = b % 4;
    const f = Math.floor((b + 8) / 25);
    const g = Math.floor((b - f + 1) / 3);
    const h = (19 * a + b - d - g + 15) % 30;
    const ii = Math.floor(c / 4);
    const k = c % 4;
    const l = (32 + 2 * e + 2 * ii - h - k) % 7;
    const m = Math.floor((a + 11 * h + 22 * l) / 451);
    const eMonth = Math.floor((h + l - 7 * m + 114) / 31);
    const eDay   = ((h + l - 7 * m + 114) % 31) + 1;
    const easter = new Date(year, eMonth - 1, eDay);

    const shift = (n: number): string => {
      const r = new Date(easter);
      r.setDate(r.getDate() + n);
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

  getHolidayLabel(day: MonthDay): string | null {
    return this._computeHolidays(day.date.getFullYear()).get(day.iso) ?? null;
  }

  // ── Chargement absences mensuel ───────────────────────────────────────────

  ngOnChanges(changes: SimpleChanges) {
    if (changes['currentMonth'] && this.currentMonth) {
      const y = this.currentMonth.getFullYear();
      const m = String(this.currentMonth.getMonth() + 1).padStart(2, '0');
      this.planningService.getMonthlyAbsenceSummary(`${y}-${m}`).subscribe({
        next: summary => { this._absenceSummary = summary; },
        error: () => {},
      });
    }
  }

  // ── Grille calendrier ─────────────────────────────────────────────────────

  get calendarDays(): MonthDay[] {
    const year  = this.currentMonth.getFullYear();
    const month = this.currentMonth.getMonth();

    const firstOfMonth = new Date(year, month, 1);
    const startOffset  = (firstOfMonth.getDay() + 6) % 7;
    const gridStart    = new Date(year, month, 1 - startOffset);

    const days: MonthDay[] = [];
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    for (let i = 0; i < 42; i++) {
      const d = new Date(gridStart);
      d.setDate(gridStart.getDate() + i);
      const iso = this.toIso(d);

      const explicitStatus = this._dayStatuses.find(s => s.date === iso) ?? null;
      const dayStatus = explicitStatus ?? this._sundayStatus(d);

      days.push({
        date: d,
        iso,
        isCurrentMonth: d.getMonth() === month,
        isToday: d.getTime() === today.getTime(),
        isPast:  d.getTime() < today.getTime(),
        shifts: this._allShifts.filter(s => s.start_datetime.startsWith(iso)),
        dayStatus,
      });
    }

    const last = days[34];
    if (!last.isCurrentMonth) return days.slice(0, 35);
    return days;
  }

  // ── Popup statut ──────────────────────────────────────────────────────────

  openStatusPopup(day: MonthDay, event: MouseEvent) {
    event.stopPropagation();
    if (!this.isManager || day.isPast || !day.isCurrentMonth) return;
    this.popupDay = this.popupDay?.iso === day.iso ? null : day;
  }

  setOpenClosed(newStatus: 'open' | 'closed') {
    if (!this.popupDay || this.savingStatus) return;
    const day = this.popupDay;
    if (day.dayStatus?.status === newStatus) return;

    // Fermé désactive les gardes (garde = ouvert)
    const dto: Record<string, unknown> = { status: newStatus };
    if (newStatus === 'closed') {
      dto['on_call_day']   = false;
      dto['on_call_night'] = false;
    }

    this.savingStatus = true;
    this.planningService.setDayStatus(day.iso, dto as any).subscribe({
      next: updated => { this._updateLocal(day.iso, updated); this.savingStatus = false; },
      error: () => { this.savingStatus = false; },
    });
  }

  toggleOnCallDay() {
    if (!this.popupDay || this.savingStatus) return;
    const day    = this.popupDay;
    const newVal = !(day.dayStatus?.on_call_day ?? false);
    const dto: Record<string, unknown> = { on_call_day: newVal };
    if (newVal) dto['status'] = 'open'; // garde = ouvert
    this.savingStatus = true;
    this.planningService.setDayStatus(day.iso, dto as any).subscribe({
      next: updated => { this._updateLocal(day.iso, updated); this.savingStatus = false; },
      error: () => { this.savingStatus = false; },
    });
  }

  toggleOnCallNight() {
    if (!this.popupDay || this.savingStatus) return;
    const day    = this.popupDay;
    const newVal = !(day.dayStatus?.on_call_night ?? false);
    const dto: Record<string, unknown> = { on_call_night: newVal };
    if (newVal) dto['status'] = 'open'; // garde = ouvert
    this.savingStatus = true;
    this.planningService.setDayStatus(day.iso, dto as any).subscribe({
      next: updated => { this._updateLocal(day.iso, updated); this.savingStatus = false; },
      error: () => { this.savingStatus = false; },
    });
  }

  /** Retourne un statut virtuel pour les dimanches sans entrée explicite :
   *  - on_call_sunday activé → garde de jour (ouvert)
   *  - sinon              → fermé
   */
  private _sundayStatus(d: Date): PharmacyDayStatus | null {
    if (d.getDay() !== 0) return null;  // pas dimanche
    const iso = this.toIso(d);
    if (this.settings?.on_call_sunday) {
      return { id: -1, date: iso, status: 'open',   on_call_day: true,  on_call_night: false, note: '' };
    }
    return   { id: -1, date: iso, status: 'closed', on_call_day: false, on_call_night: false, note: '' };
  }

  private _updateLocal(iso: string, updated: PharmacyDayStatus) {
    const idx = this._dayStatuses.findIndex(s => s.date === iso);
    if (idx >= 0) {
      this._dayStatuses = [
        ...this._dayStatuses.slice(0, idx),
        updated,
        ...this._dayStatuses.slice(idx + 1),
      ];
    } else {
      this._dayStatuses = [...this._dayStatuses, updated];
    }
    if (this.popupDay?.iso === iso) {
      this.popupDay = { ...this.popupDay, dayStatus: updated };
    }
    this.dayStatusChanged.emit();
  }

  @HostListener('document:click')
  closePopup() {
    this.popupDay = null;
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  private toIso(d: Date): string {
    const p = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
  }

  getCollaboratorDots(day: MonthDay): { color: string; name: string }[] {
    const seen = new Set<number>();
    const dots: { color: string; name: string }[] = [];
    for (const s of day.shifts) {
      if (!s.collaborator) continue;
      if (!seen.has(s.collaborator.id)) {
        seen.add(s.collaborator.id);
        dots.push({
          color: s.collaborator.color,
          name:  `${s.collaborator.first_name} ${s.collaborator.last_name}`,
        });
      }
    }
    return dots;
  }

  getAbsenceStyle(color: string): Record<string, string> {
    const c = resolveColor(color);
    return { 'background-color': c.light, 'color': c.text };
  }

  /** Badges J / N / F(fermé) / F(férié) dans la cellule */
  getStatusBadges(day: MonthDay): { label: string; cls: string; title: string }[] {
    const badges: { label: string; cls: string; title: string }[] = [];

    // Badge Férié (en premier, en ambré)
    const holidayLabel = this.getHolidayLabel(day);
    if (holidayLabel) {
      badges.push({ label: 'F', cls: 'badge-ferie', title: holidayLabel });
    }

    if (!day.dayStatus) return badges;
    if (day.dayStatus.on_call_day)
      badges.push({ label: 'J', cls: 'badge-oncall-day', title: 'Garde de jour' });
    if (day.dayStatus.on_call_night)
      badges.push({ label: 'N', cls: 'badge-oncall-night', title: 'Garde de nuit' });
    if (day.dayStatus.status === 'closed' && !day.dayStatus.on_call_day && !day.dayStatus.on_call_night && !holidayLabel)
      badges.push({ label: 'F', cls: 'badge-closed', title: 'Fermé' });
    return badges;
  }

  getCellClass(day: MonthDay): string {
    const isFerie = !!this.getHolidayLabel(day);
    if (!day.dayStatus) return isFerie ? 'month-cell-ferie' : '';
    if (day.dayStatus.on_call_day && day.dayStatus.on_call_night) return 'month-cell-oncall-both';
    if (day.dayStatus.on_call_day)   return 'month-cell-oncall-day';
    if (day.dayStatus.on_call_night) return 'month-cell-oncall-night';
    if (day.dayStatus.status === 'closed') return isFerie ? 'month-cell-ferie' : 'month-cell-closed';
    return isFerie ? 'month-cell-ferie' : '';
  }

  get calendarRows(): { weekNumber: number; days: MonthDay[] }[] {
    const days = this.calendarDays;
    const rows: { weekNumber: number; days: MonthDay[] }[] = [];
    for (let i = 0; i < days.length; i += 7) {
      rows.push({
        weekNumber: this.getIsoWeekNumber(days[i].date),
        days: days.slice(i, i + 7),
      });
    }
    return rows;
  }

  getIsoWeekNumber(d: Date): number {
    const date = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
    date.setUTCDate(date.getUTCDate() + 4 - (date.getUTCDay() || 7));
    const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
    return Math.ceil((((date.getTime() - yearStart.getTime()) / 86400000) + 1) / 7);
  }

  onDayClick(day: MonthDay) {
    if (day.isCurrentMonth) {
      this.dayClicked.emit(day.date);
    }
  }

  currentStatus(day: MonthDay): 'open' | 'closed' {
    return day.dayStatus?.status ?? 'open';
  }

  getDayAbsences(day: MonthDay): MonthlyAbsenceEntry[] {
    return this._absenceSummary[day.iso] ?? [];
  }

  getAbsenceInitials(day: MonthDay): { initials: string; color: string; type: string }[] {
    return this.getDayAbsences(day).slice(0, 3).map(a => ({
      initials: a.initials,
      color:    a.color,
      type:     a.type,
    }));
  }

  getAbsenceOverflow(day: MonthDay): number {
    const total = this.getDayAbsences(day).length;
    return total > 3 ? total - 3 : 0;
  }

  guardDayLabel(): string {
    if (!this.settings?.on_call_day_start || !this.settings?.on_call_day_end) return 'Garde de jour';
    return `Garde jour · ${this.settings.on_call_day_start.substring(0, 5)}–${this.settings.on_call_day_end.substring(0, 5)}`;
  }

  guardNightLabel(): string {
    if (!this.settings?.on_call_night_start || !this.settings?.on_call_night_end) return 'Garde de nuit';
    return `Garde nuit · ${this.settings.on_call_night_start.substring(0, 5)}–${this.settings.on_call_night_end.substring(0, 5)}`;
  }
}
