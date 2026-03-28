import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subject, Subscription, forkJoin } from 'rxjs';
import { takeUntil } from 'rxjs/operators';

import { AuthService } from '../../core/auth/auth.service';
import { CollaboratorService, Collaborator } from '../../core/services/collaborator.service';
import { PlanningService, WeekResponse, OpeningHours, Shift } from '../../core/services/planning.service';
import { PinModalComponent } from '../messaging/components/pin-modal/pin-modal.component';
import { WeekViewComponent } from './components/week-view/week-view.component';
import { MonthViewComponent } from './components/month-view/month-view.component';
import { AbsenceModalComponent } from './components/absence-modal/absence-modal.component';
import { PlanningSettingsComponent } from './components/planning-settings/planning-settings.component';
import { TemplateModalComponent } from './components/template-modal/template-modal.component';
import { TimeAdjustmentsComponent } from './components/time-adjustments/time-adjustments.component';
import { PlanningAnalyticsComponent } from './components/planning-analytics/planning-analytics.component';
import { ShiftDrawerComponent } from './components/shift-drawer/shift-drawer.component';
import { PlanningSettings } from '../../core/services/planning.service';

@Component({
  selector: 'app-planning',
  standalone: true,
  imports: [CommonModule, PinModalComponent, WeekViewComponent, MonthViewComponent, AbsenceModalComponent, PlanningSettingsComponent, TemplateModalComponent, TimeAdjustmentsComponent, PlanningAnalyticsComponent, ShiftDrawerComponent],
  templateUrl: './planning.component.html',
  styleUrl: './planning.component.css',
})
export class PlanningComponent implements OnInit, OnDestroy {
  private authService         = inject(AuthService);
  private collaboratorService = inject(CollaboratorService);
  private planningService     = inject(PlanningService);
  private destroy$            = new Subject<void>();
  private subs                = new Subscription();

  // ── Session collaborateur ─────────────────────────────────────────────────
  team: Collaborator[]              = [];
  activeCollaborator: Collaborator | null = null;
  pendingCollaborator: Collaborator | null = null;
  showCollaboratorPicker            = false;
  showPinModal                      = false;
  isManager                         = false;

  // ── Vue semaine ───────────────────────────────────────────────────────────
  weekData: WeekResponse | null = null;
  currentWeekStr                = '';
  currentMonday: Date           = this.getMonday(new Date());

  // ── Vue mois ──────────────────────────────────────────────────────────────
  viewMode: 'week' | 'month'    = 'week';
  weekTimelineMode: '24h' | 'zoom' = 'zoom';
  currentMonth: Date            = new Date(new Date().getFullYear(), new Date().getMonth(), 1);
  monthWeeks: WeekResponse[]    = [];

  loading                = false;
  showFullTeam           = false;
  showAbsenceModal       = false;
  showSettingsModal      = false;
  showTemplateModal      = false;
  showAdjustmentsModal   = false;
  adjustmentsTab: 'list' | 'create' | 'absence' = 'list';
  adjustmentsMode: 'adjustments' | 'absence' = 'adjustments';
  showAnalyticsPanel     = false;
  planningSettings: PlanningSettings | null = null;
  openingHours: OpeningHours[] = [];

  // ── Drawer shift ──────────────────────────────────────────────────────────
  showShiftDrawer     = false;
  drawerShift: Shift | null = null;
  drawerDate: string | null = null;
  drawerCollaboratorId: number | null = null;

  // ── Filtrage collaborateurs (pills niveau 2) ───────────────────────────────
  selectedCollaboratorIds: number[] = [];
  showCollabDropdown = false;
  readonly PILL_MAX = 4;

  ngOnInit() {
    this.currentWeekStr = this.toIsoWeek(this.currentMonday);
    this.planningService.getSettings().subscribe(s => { this.planningSettings = s; });
    this.planningService.getOpeningHours(this.currentWeekStr).subscribe(h => { this.openingHours = h; });

    this.collaboratorService.getTeam().subscribe(team => {
      this.team = team;
      this.subs.add(
        this.authService.collaborator$.subscribe(id => {
          const found = id ? team.find(c => c.id === id) ?? null : null;
          if (found?.id === this.activeCollaborator?.id) return;
          this.destroy$.next();
          this.showPinModal = false;
          this.pendingCollaborator = null;
          if (found) {
            this.activeCollaborator = found;
            this.showCollaboratorPicker = false;
            this.isManager = found.can_manage_planning ?? false;
            this.showFullTeam = false;
            if (!this.isManager) this.viewMode = 'week';
            this.loadCurrent();
          } else {
            this.activeCollaborator = null;
            this.isManager = false;
            this.showCollaboratorPicker = true;
          }
        })
      );
    });
  }

  // ── Collaborateur ─────────────────────────────────────────────────────────

  selectCollaborator(collab: Collaborator) {
    this.pendingCollaborator = collab;
    this.showPinModal = true;
  }

  onPinValidated() {
    if (!this.pendingCollaborator) return;
    this.authService.setCurrentCollaboratorId(this.pendingCollaborator.id!);
    this.showPinModal = false;
    this.pendingCollaborator = null;
  }

  onPinCancelled() {
    this.showPinModal = false;
    this.pendingCollaborator = null;
  }

  onSettingsClosed() {
    this.showSettingsModal = false;
    this.planningService.getSettings().subscribe(s => { this.planningSettings = s; });
    this.planningService.getOpeningHours(this.currentWeekStr).subscribe(h => { this.openingHours = h; });
  }

  // ── Drawer shift ──────────────────────────────────────────────────────────

  openDrawerForShift(shift: Shift) {
    this.drawerShift         = shift;
    this.drawerDate          = null;
    this.drawerCollaboratorId = null;
    this.showShiftDrawer     = true;
  }

  openDrawerForCell(event: { collaboratorId: number; date: string }) {
    this.drawerShift         = null;
    this.drawerDate          = event.date;
    this.drawerCollaboratorId = event.collaboratorId;
    this.showShiftDrawer     = true;
  }

  onDrawerSaved(_shift: Shift) {
    this.loadWeek();
  }

  onDrawerDeleted(_id: number) {
    this.loadWeek();
  }

  onDrawerTransformed() {
    this.loadWeek();
  }

  closeDrawer() {
    this.showShiftDrawer = false;
    this.drawerShift     = null;
  }

  changeCollaborator() {
    this.authService.clearCurrentCollaborator();
    this.activeCollaborator = null;
    this.isManager = false;
    this.destroy$.next();
    this.showCollaboratorPicker = true;
  }

  // ── Filtrage par pills ────────────────────────────────────────────────────

  get isAllSelected(): boolean {
    return this.selectedCollaboratorIds.length === 0;
  }

  isCollaboratorSelected(id: number): boolean {
    return this.selectedCollaboratorIds.includes(id);
  }

  selectAll(): void {
    this.selectedCollaboratorIds = [];
  }

  toggleCollaboratorFilter(id: number): void {
    const idx = this.selectedCollaboratorIds.indexOf(id);
    if (idx === -1) {
      this.selectedCollaboratorIds = [...this.selectedCollaboratorIds, id];
    } else {
      this.selectedCollaboratorIds = this.selectedCollaboratorIds.filter(i => i !== id);
    }
  }

  get filteredCollaboratorIds(): number[] | null {
    return this.selectedCollaboratorIds.length > 0 ? [...this.selectedCollaboratorIds] : null;
  }

  get visibleTeamPills(): Collaborator[] {
    return this.team.slice(0, this.PILL_MAX);
  }

  get overflowTeam(): Collaborator[] {
    return this.team.slice(this.PILL_MAX);
  }

  hasOverflowSelected(): boolean {
    return this.overflowTeam.some(c => this.selectedCollaboratorIds.includes(c.id!));
  }

  // ── Métriques ─────────────────────────────────────────────────────────────

  get totalPlannedHours(): number {
    if (!this.weekData) return 0;
    const base = this.filteredCollaboratorIds
      ? this.weekData.summary.filter(s => this.filteredCollaboratorIds!.includes(s.collaborator_id))
      : this.weekData.summary;
    return base.reduce((acc, s) => acc + (s.planned_h ?? 0), 0);
  }

  get absenceCount(): number {
    if (!this.weekData) return 0;
    const base = this.filteredCollaboratorIds
      ? this.weekData.summary.filter(s => this.filteredCollaboratorIds!.includes(s.collaborator_id))
      : this.weekData.summary;
    return base.reduce((acc, s) => acc + (s.absences?.length ?? 0), 0);
  }

  // ── Toggle vue ────────────────────────────────────────────────────────────

  setView(mode: 'week' | 'month') {
    this.viewMode = mode;
    if (mode === 'month') {
      this.currentMonth = new Date(this.currentMonday.getFullYear(), this.currentMonday.getMonth(), 1);
      this.loadMonth();
    } else {
      this.loadWeek();
    }
  }

  /** Segmented control 3 états : 'week' | 'month' | '24h' */
  setViewMode(mode: 'week' | 'month' | '24h'): void {
    if (mode === 'month') {
      this.setView('month');
    } else if (mode === 'week') {
      this.weekTimelineMode = 'zoom';
      if (this.viewMode !== 'week') this.setView('week');
    } else {
      this.weekTimelineMode = '24h';
      if (this.viewMode !== 'week') this.setView('week');
    }
  }

  get currentViewMode(): 'week' | 'month' | '24h' {
    if (this.viewMode === 'month') return 'month';
    return this.weekTimelineMode === '24h' ? '24h' : 'week';
  }

  // ── Navigation semaine ────────────────────────────────────────────────────

  prevWeek() {
    this.currentMonday = new Date(this.currentMonday.getTime() - 7 * 86400000);
    this.currentWeekStr = this.toIsoWeek(this.currentMonday);
    this.loadWeek();
  }

  nextWeek() {
    this.currentMonday = new Date(this.currentMonday.getTime() + 7 * 86400000);
    this.currentWeekStr = this.toIsoWeek(this.currentMonday);
    this.loadWeek();
  }

  goToCurrentWeek() {
    this.currentMonday = this.getMonday(new Date());
    this.currentWeekStr = this.toIsoWeek(this.currentMonday);
    this.loadWeek();
  }

  // ── Navigation mois ───────────────────────────────────────────────────────

  prevMonth() {
    this.currentMonth = new Date(this.currentMonth.getFullYear(), this.currentMonth.getMonth() - 1, 1);
    this.loadMonth();
  }

  nextMonth() {
    this.currentMonth = new Date(this.currentMonth.getFullYear(), this.currentMonth.getMonth() + 1, 1);
    this.loadMonth();
  }

  onDayClicked(day: Date) {
    // Basculer en vue semaine sur la semaine du jour cliqué
    this.currentMonday = this.getMonday(day);
    this.currentWeekStr = this.toIsoWeek(this.currentMonday);
    this.viewMode = 'week';
    this.loadWeek();
  }

  // ── Chargement données ────────────────────────────────────────────────────

  loadCurrent() {
    if (this.viewMode === 'week') {
      this.loadWeek();
    } else {
      this.loadMonth();
    }
  }

  loadWeek() {
    this.loading = true;
    this.planningService.getOpeningHours(this.currentWeekStr).subscribe(h => { this.openingHours = h; });
    this.planningService.getWeek(this.currentWeekStr)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: data => {
          this.weekData = data;
          this.loading = false;
          // Si le drawer est ouvert sur un shift, on le synchronise avec
          // la version fraîche de weekData (même ID) pour que ngOnChanges
          // mette à jour les champs du formulaire sans réinitialiser le badge.
          if (this.showShiftDrawer && this.drawerShift) {
            const fresh = data.shifts.find(s => s.id === this.drawerShift!.id);
            if (fresh) this.drawerShift = fresh;
          }
        },
        error: () => { this.loading = false; },
      });
  }

  loadMonth() {
    this.loading = true;
    const weeks = this.getWeeksOfMonth(this.currentMonth);
    const requests = weeks.map(w => this.planningService.getWeek(w));

    forkJoin(requests)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next:  results => { this.monthWeeks = results; this.loading = false; },
        error: ()      => { this.loading = false; },
      });
  }

  onShiftChanged() {
    this.loadWeek();
  }

  get isWeekFullyPublished(): boolean {
    return !!this.weekData &&
      this.weekData.shifts.length > 0 &&
      this.weekData.shifts.every(s => s.is_published);
  }

  get hasUnpublishedShifts(): boolean {
    return !!this.weekData && this.weekData.shifts.some(s => !s.is_published);
  }

  publishWeek() {
    this.planningService.publishWeek(this.currentWeekStr).subscribe(() => this.loadWeek());
  }

  unpublishWeek() {
    this.planningService.unpublishWeek(this.currentWeekStr).subscribe(() => this.loadWeek());
  }

  printWeek() {
    window.print();
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  /** Retourne les ISO-weeks du mois (ex: ['2025-W09', '2025-W10', ...]) */
  getWeeksOfMonth(month: Date): string[] {
    const year  = month.getFullYear();
    const m     = month.getMonth();
    const weeks = new Set<string>();

    // Parcourir tous les jours du mois
    for (let d = 1; d <= 31; d++) {
      const date = new Date(year, m, d);
      if (date.getMonth() !== m) break;
      const monday = this.getMonday(date);
      weeks.add(this.toIsoWeek(monday));
    }
    return Array.from(weeks);
  }

  getMonday(d: Date): Date {
    const day = d.getDay();
    const diff = (day === 0 ? -6 : 1 - day);
    const monday = new Date(d);
    monday.setDate(d.getDate() + diff);
    monday.setHours(0, 0, 0, 0);
    return monday;
  }

  toIsoWeek(monday: Date): string {
    const jan4 = new Date(monday.getFullYear(), 0, 4);
    const startOfWeek1 = new Date(jan4);
    startOfWeek1.setDate(jan4.getDate() - ((jan4.getDay() + 6) % 7));
    const weekNum = Math.round((monday.getTime() - startOfWeek1.getTime()) / (7 * 86400000)) + 1;
    return `${monday.getFullYear()}-W${String(weekNum).padStart(2, '0')}`;
  }

  getWeekLabel(): string {
    const sunday = new Date(this.currentMonday.getTime() + 6 * 86400000);
    const fmtDay      = (d: Date) => d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' });
    const fmtDayShort = (d: Date) => d.toLocaleDateString('fr-FR', { day: 'numeric' });
    const sameMonth   = this.currentMonday.getMonth() === sunday.getMonth();
    if (sameMonth) {
      return `${fmtDayShort(this.currentMonday)} – ${fmtDay(sunday)} ${this.currentMonday.getFullYear()}`;
    }
    return `${fmtDay(this.currentMonday)} – ${fmtDay(sunday)} ${this.currentMonday.getFullYear()}`;
  }

  getMonthLabel(): string {
    return this.currentMonth.toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' });
  }

  isCurrentWeek(): boolean {
    return this.currentMonday.toDateString() === this.getMonday(new Date()).toDateString();
  }

  get currentWeekNumber(): number {
    const d = new Date(Date.UTC(
      this.currentMonday.getFullYear(),
      this.currentMonday.getMonth(),
      this.currentMonday.getDate(),
    ));
    d.setUTCDate(d.getUTCDate() + 4 - (d.getUTCDay() || 7));
    const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
    return Math.ceil((((d.getTime() - yearStart.getTime()) / 86400000) + 1) / 7);
  }

  getInitials(collab: Collaborator): string {
    return `${collab.first_name.charAt(0)}${collab.last_name.charAt(0)}`.toUpperCase();
  }


  ngOnDestroy() {
    this.subs.unsubscribe();
    this.destroy$.next();
    this.destroy$.complete();
  }
}
