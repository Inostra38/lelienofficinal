import { Component, Input, Output, EventEmitter, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  PlanningService,
  WeekTemplate,
  TemplateShift,
  PlanningSettings,
  OpeningHours,
} from '../../../../core/services/planning.service';
import { CollaboratorService, Collaborator } from '../../../../core/services/collaborator.service';

@Component({
  selector: 'app-template-modal',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './template-modal.component.html',
  styleUrl: './template-modal.component.css',
})
export class TemplateModalComponent implements OnInit {
  @Input() currentWeekStr   = '';
  @Input() planningSettings: PlanningSettings | null = null;

  applyWeek  = '';   // semaine ISO sélectionnée pour l'application (ex: "2026-W12")
  applyForce = false;

  @Output() closed      = new EventEmitter<void>();
  @Output() weekChanged = new EventEmitter<void>();

  private planningService     = inject(PlanningService);
  private collaboratorService = inject(CollaboratorService);

  activeLetter: 'A' | 'B' | 'C' | 'D' = 'A';
  template: WeekTemplate | null = null;
  team: Collaborator[] = [];
  openingHours: OpeningHours[] = [];
  loading  = false;
  applying = false;
  applyResult: { created: number; skipped: number; replaced: number; absence_protected: number; day_protected: number } | null = null;

  showAddForm   = false;
  editingShift: TemplateShift | null = null;
  addSubmitting = false;
  addError      = '';

  get isEditing(): boolean { return !!this.editingShift; }
  addForm = {
    collaborator_id: 0,
    day_of_week:     0,
    start_time:      '09:00',
    end_time:        '19:00',
    note:            '',
  };

  readonly DAY_NAMES = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche'];
  readonly hoursArr  = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, '0'));
  readonly minsArr   = ['00','05','10','15','20','25','30','35','40','45','50','55'];

  getH(field: 'start_time' | 'end_time'): string { return (this.addForm[field] || '00:00').split(':')[0]; }
  getM(field: 'start_time' | 'end_time'): string { return (this.addForm[field] || '00:00').split(':')[1]; }
  setH(field: 'start_time' | 'end_time', v: string) { this.addForm[field] = `${v}:${this.getM(field)}`; }
  setM(field: 'start_time' | 'end_time', v: string) { this.addForm[field] = `${this.getH(field)}:${v}`; }

  // ── Timeline ──────────────────────────────────────────────────────────────

  readonly dayStartHour = 0;
  readonly dayEndHour   = 24;
  readonly totalHours   = 24;

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

  // ── Lifecycle ─────────────────────────────────────────────────────────────

  ngOnInit() {
    this.applyWeek = this.currentWeekStr;
    this.planningService.getOpeningHours().subscribe(h => { this.openingHours = h; });
    this.collaboratorService.getTeam().subscribe(team => {
      this.team = team;
      if (team.length > 0) this.addForm.collaborator_id = team[0].id!;
      this.loadTemplate();
    });
  }

  // ── Lettres disponibles ───────────────────────────────────────────────────

  readonly letters: ('A' | 'B' | 'C' | 'D')[] = ['A', 'B', 'C', 'D'];

  setLetter(letter: 'A' | 'B' | 'C' | 'D') {
    this.activeLetter  = letter;
    this.template      = null;
    this.applyResult   = null;
    this.showAddForm   = false;
    this.loadTemplate();
  }

  loadTemplate() {
    this.loading = true;
    this.planningService.getTemplate(this.activeLetter).subscribe({
      next:  t  => { this.template = t; this.loading = false; },
      error: () => { this.loading = false; },
    });
  }

  // ── apply_from ────────────────────────────────────────────────────────────

  saveApplyFrom(dateStr: string) {
    if (!dateStr) return;
    this.planningService.updateTemplate(this.activeLetter, { apply_from: dateStr }).subscribe(t => {
      if (this.template) this.template.apply_from = t.apply_from;
    });
  }

  // ── Shifts template ───────────────────────────────────────────────────────

  getShiftsForDay(dayOfWeek: number): TemplateShift[] {
    return this.template?.shifts.filter(s => s.day_of_week === dayOfWeek) ?? [];
  }

  getCollaboratorsForDay(dayOfWeek: number): Collaborator[] {
    const shifts = this.getShiftsForDay(dayOfWeek);
    const seen = new Set<number>();
    const result: Collaborator[] = [];
    for (const s of shifts) {
      if (!seen.has(s.collaborator.id)) {
        seen.add(s.collaborator.id);
        const collab = this.team.find(c => c.id === s.collaborator.id);
        if (collab) result.push(collab);
      }
    }
    return result;
  }

  getShiftsForCollab(dayOfWeek: number, collabId: number): TemplateShift[] {
    return this.getShiftsForDay(dayOfWeek).filter(s => s.collaborator.id === collabId);
  }

  // ── Timeline positioning ──────────────────────────────────────────────────

  get hours(): number[] {
    return [0, 3, 6, 9, 12, 15, 18, 21, 24];
  }

  getHourLeft(hour: number): number {
    return ((hour - this.dayStartHour) / this.totalHours) * 100;
  }

  getTShiftLeft(shift: TemplateShift): number {
    const [h, m] = shift.start_time.split(':').map(Number);
    const minutes = (h - this.dayStartHour) * 60 + m;
    return Math.max(0, (minutes / (this.totalHours * 60)) * 100);
  }

  getTShiftWidth(shift: TemplateShift): number {
    const [sh, sm] = shift.start_time.split(':').map(Number);
    const [eh, em] = shift.end_time.split(':').map(Number);
    const duration = (eh * 60 + em) - (sh * 60 + sm);
    const left = this.getTShiftLeft(shift);
    return Math.min(100 - left, (duration / (this.totalHours * 60)) * 100);
  }

  getColor(color: string): { base: string; light: string; text: string } {
    return this.colorPalette[color] ?? this.colorPalette['gray'];
  }

  getShortName(collab: Collaborator): string {
    return `${collab.first_name} ${collab.last_name.charAt(0)}.`;
  }

  getBgClass(color: string): string {
    return `bg-${color}-500`;
  }

  // ── Ajout shift template ──────────────────────────────────────────────────

  openAddForm(dayOfWeek: number) {
    this.editingShift        = null;
    this.addForm.day_of_week = dayOfWeek;
    this.addForm.collaborator_id = this.team[0]?.id ?? 0;
    this.addForm.start_time  = '09:00';
    this.addForm.end_time    = '19:00';
    this.addForm.note        = '';
    this.addError            = '';
    this.showAddForm         = true;
  }

  openEditForm(shift: TemplateShift) {
    this.editingShift            = shift;
    this.addForm.collaborator_id = shift.collaborator.id;
    this.addForm.day_of_week     = shift.day_of_week;
    this.addForm.start_time      = shift.start_time.substring(0, 5);
    this.addForm.end_time        = shift.end_time.substring(0, 5);
    this.addForm.note            = shift.note ?? '';
    this.addError                = '';
    this.showAddForm             = true;
  }

  roundTo5(field: 'start_time' | 'end_time') {
    const val = this.addForm[field];
    if (!val) return;
    const [h, m] = val.split(':').map(Number);
    const r = Math.round(m / 5) * 5;
    const mins  = r === 60 ? 0 : r;
    const hours = r === 60 ? (h + 1) % 24 : h;
    this.addForm[field] = `${String(hours).padStart(2, '0')}:${String(mins).padStart(2, '0')}`;
  }

  submitAdd() {
    if (!this.addForm.collaborator_id) {
      this.addError = 'Sélectionnez un collaborateur.';
      return;
    }
    if (this.addForm.end_time <= this.addForm.start_time) {
      this.addError = 'L\'heure de fin doit être après l\'heure de début.';
      return;
    }
    this.addSubmitting = true;
    this.addError      = '';

    const dto = {
      collaborator_id: this.addForm.collaborator_id,
      day_of_week:     this.addForm.day_of_week,
      start_time:      this.addForm.start_time + ':00',
      end_time:        this.addForm.end_time   + ':00',
      note:            this.addForm.note,
    };

    const request$ = this.editingShift
      ? this.planningService.updateTemplateShift(this.activeLetter, this.editingShift.id, dto)
      : this.planningService.createTemplateShift(this.activeLetter, dto);

    request$.subscribe({
      next: () => {
        this.addSubmitting = false;
        this.showAddForm   = false;
        this.editingShift  = null;
        this.loadTemplate();
      },
      error: () => {
        this.addSubmitting = false;
        this.addError = this.editingShift ? 'Erreur lors de la modification.' : 'Erreur lors de la création.';
      },
    });
  }

  deleteShift(shiftId: number) {
    if (!confirm('Supprimer ce shift du template ?')) return;
    this.planningService.deleteTemplateShift(this.activeLetter, shiftId).subscribe(() => {
      this.showAddForm  = false;
      this.editingShift = null;
      this.loadTemplate();
    });
  }

  // ── Appliquer le template ─────────────────────────────────────────────────

  applyToWeek() {
    const week = this.applyWeek || this.currentWeekStr;
    if (!week) return;
    this.applying     = true;
    this.applyResult  = null;

    this.planningService.applyTemplate(this.activeLetter, week, this.applyForce).subscribe({
      next: res => {
        this.applying     = false;
        this.applyResult  = { created: res.created, skipped: res.skipped, replaced: res.replaced ?? 0, absence_protected: res.absence_protected ?? 0, day_protected: res.day_protected ?? 0 };
        this.weekChanged.emit();
      },
      error: () => { this.applying = false; },
    });
  }

  // ── Gradient horaires d'ouverture ─────────────────────────────────────────

  getRowGradient(dayOfWeek: number): string {
    if (dayOfWeek === 6) return '#eef2ff'; // dimanche toujours fermé
    const slots = this.openingHours
      .filter(h => h.day_of_week === dayOfWeek)
      .map(h => ({ start: this._timeToMins(h.start_time), end: this._timeToMins(h.end_time) }))
      .sort((a, b) => a.start - b.start);
    if (slots.length === 0) return '#eef2ff';
    const total = 24 * 60;
    const pct = (m: number) => ((m / total) * 100).toFixed(3);
    const stops: string[] = [];
    let cur = 0;
    for (const { start, end } of slots) {
      if (start > cur) stops.push(`#eef2ff ${pct(cur)}%, #eef2ff ${pct(start)}%`);
      stops.push(`#ffffff ${pct(start)}%, #ffffff ${pct(end)}%`);
      cur = end;
    }
    if (cur < total) stops.push(`#eef2ff ${pct(cur)}%, #eef2ff 100%`);
    return `linear-gradient(to right, ${stops.join(', ')})`;
  }

  private _timeToMins(timeStr: string): number {
    const [h, m] = timeStr.split(':').map(Number);
    return h * 60 + m;
  }

  // ── Heures hebdomadaires par collaborateur (calculées localement) ──────────

  getCollabWeekHours(collabId: number): number {
    if (!this.template) return 0;
    return this.template.shifts
      .filter(s => s.collaborator.id === collabId)
      .reduce((acc, s) => {
        const [sh, sm] = s.start_time.split(':').map(Number);
        const [eh, em] = s.end_time.split(':').map(Number);
        return acc + ((eh * 60 + em) - (sh * 60 + sm)) / 60;
      }, 0);
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  formatTime(timeStr: string): string {
    return timeStr.substring(0, 5);
  }
}
