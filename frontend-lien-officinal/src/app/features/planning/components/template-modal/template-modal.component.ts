import { Component, Input, Output, EventEmitter, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { from, forkJoin, Observable } from 'rxjs';
import { concatMap } from 'rxjs/operators';
import {
  PlanningService,
  WeekTemplate,
  TemplateShift,
  PlanningSettings,
  OpeningHours,
} from '../../../../core/services/planning.service';
import { resolveColor } from '../../../../core/utils/collaborator-colors';
import { CollaboratorService, Collaborator } from '../../../../core/services/collaborator.service';
import { ConfirmService } from '../../../../core/services/confirm.service';
import { ConstraintManagerComponent } from '../constraint-manager/constraint-manager.component';
import { TemplateAiAssistantComponent } from '../template-ai-assistant/template-ai-assistant.component';

type Letter = 'A' | 'B' | 'C' | 'D';

@Component({
  selector: 'app-template-modal',
  standalone: true,
  imports: [CommonModule, FormsModule, ConstraintManagerComponent, TemplateAiAssistantComponent],
  templateUrl: './template-modal.component.html',
  styleUrl: './template-modal.component.css',
})
export class TemplateModalComponent implements OnInit {
  @Input() currentWeekStr   = '';
  @Input() planningSettings: PlanningSettings | null = null;

  @Output() closed      = new EventEmitter<void>();
  @Output() weekChanged = new EventEmitter<void>();

  private planningService     = inject(PlanningService);
  private collaboratorService = inject(CollaboratorService);
  private confirmService      = inject(ConfirmService);

  readonly letters: Letter[] = ['A', 'B', 'C', 'D'];

  // Toutes les templates chargées en parallèle
  templates: Record<Letter, WeekTemplate | null> = { A: null, B: null, C: null, D: null };
  loading = false;

  // État apply par lettre
  applyWeeks:   Record<Letter, string>   = { A: '', B: '', C: '', D: '' };
  applyForces:  Record<Letter, boolean>  = { A: false, B: false, C: false, D: false };
  applyResults: Record<Letter, { created: number; skipped: number; replaced: number; absence_protected: number; day_protected: number; violations: { shift_date: string; collaborator: string; error: string }[] } | null> = { A: null, B: null, C: null, D: null };
  applyings:    Record<Letter, boolean>  = { A: false, B: false, C: false, D: false };

  team: Collaborator[] = [];
  openingHours: OpeningHours[] = [];
  showAiPanel = false;

  // Prévisualisation template IA
  previewTemplate: any = null;
  previewLetter = 'A';

  // Lettre active pour le formulaire ajout/édition
  activeLetter: Letter = 'A';
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


  // ── Lifecycle ─────────────────────────────────────────────────────────────

  ngOnInit() {
    this.letters.forEach(l => { this.applyWeeks[l] = this.currentWeekStr; });
    this.planningService.getOpeningHours().subscribe(h => { this.openingHours = h; });
    this.collaboratorService.getTeam().subscribe(team => {
      this.team = team;
      if (team.length > 0) this.addForm.collaborator_id = team[0].id!;
      this.loadAllTemplates();
    });
  }

  // ── Chargement de toutes les templates ────────────────────────────────────

  loadAllTemplates() {
    this.loading = true;
    forkJoin(
      this.letters.reduce((acc, l) => {
        acc[l] = this.planningService.getTemplate(l);
        return acc;
      }, {} as Record<Letter, Observable<WeekTemplate>>)
    ).subscribe({
      next:  (result) => {
        this.letters.forEach(l => { this.templates[l] = result[l]; });
        this.loading = false;
      },
      error: () => { this.loading = false; },
    });
  }

  loadTemplate(letter: Letter) {
    this.planningService.getTemplate(letter).subscribe(t => {
      this.templates[letter] = t;
    });
  }

  // ── Shifts template ───────────────────────────────────────────────────────

  getShiftsForDay(letter: Letter, dayOfWeek: number): TemplateShift[] {
    return this.templates[letter]?.shifts.filter(s => s.day_of_week === dayOfWeek) ?? [];
  }

  getCollaboratorsForDay(letter: Letter, dayOfWeek: number): Collaborator[] {
    const shifts = this.getShiftsForDay(letter, dayOfWeek);
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

  getShiftsForCollab(letter: Letter, dayOfWeek: number, collabId: number): TemplateShift[] {
    return this.getShiftsForDay(letter, dayOfWeek).filter(s => s.collaborator.id === collabId);
  }

  getCollabWeekHours(letter: Letter, collabId: number): number {
    return (this.templates[letter]?.shifts ?? [])
      .filter(s => s.collaborator.id === collabId)
      .reduce((acc, s) => {
        const [sh, sm] = s.start_time.split(':').map(Number);
        const [eh, em] = s.end_time.split(':').map(Number);
        return acc + ((eh * 60 + em) - (sh * 60 + sm)) / 60;
      }, 0);
  }

  // ── Timeline positioning ──────────────────────────────────────────────────

  get hours(): number[] { return [0, 3, 6, 9, 12, 15, 18, 21, 24]; }

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
    return resolveColor(color);
  }

  // ── Ajout / édition shift template ───────────────────────────────────────

  openAddForm(letter: Letter, dayOfWeek: number) {
    this.activeLetter            = letter;
    this.editingShift            = null;
    this.addForm.day_of_week     = dayOfWeek;
    this.addForm.collaborator_id = this.team[0]?.id ?? 0;
    this.addForm.start_time      = '09:00';
    this.addForm.end_time        = '19:00';
    this.addForm.note            = '';
    this.addError                = '';
    this.showAddForm             = true;
  }

  openEditForm(letter: Letter, shift: TemplateShift) {
    this.activeLetter            = letter;
    this.editingShift            = shift;
    this.addForm.collaborator_id = shift.collaborator.id;
    this.addForm.day_of_week     = shift.day_of_week;
    this.addForm.start_time      = shift.start_time.substring(0, 5);
    this.addForm.end_time        = shift.end_time.substring(0, 5);
    this.addForm.note            = shift.note ?? '';
    this.addError                = '';
    this.showAddForm             = true;
  }

  submitAdd() {
    if (!this.addForm.collaborator_id) { this.addError = 'Sélectionnez un collaborateur.'; return; }
    if (this.addForm.end_time <= this.addForm.start_time) { this.addError = 'L\'heure de fin doit être après l\'heure de début.'; return; }
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
        this.loadTemplate(this.activeLetter);
      },
      error: () => {
        this.addSubmitting = false;
        this.addError = this.editingShift ? 'Erreur lors de la modification.' : 'Erreur lors de la création.';
      },
    });
  }

  async deleteShift(shiftId: number) {
    if (!await this.confirmService.ask({ title: 'Supprimer le shift', message: 'Supprimer ce shift du template ?', danger: true })) return;
    this.planningService.deleteTemplateShift(this.activeLetter, shiftId).subscribe(() => {
      this.showAddForm  = false;
      this.editingShift = null;
      this.loadTemplate(this.activeLetter);
    });
  }

  // ── Appliquer le template ─────────────────────────────────────────────────

  applyToWeek(letter: Letter) {
    const week = this.applyWeeks[letter] || this.currentWeekStr;
    if (!week) return;
    this.applyings[letter]    = true;
    this.applyResults[letter] = null;

    this.planningService.applyTemplate(letter, week, this.applyForces[letter]).subscribe({
      next: res => {
        this.applyings[letter]    = false;
        this.applyResults[letter] = { created: res.created, skipped: res.skipped, replaced: res.replaced ?? 0, absence_protected: res.absence_protected ?? 0, day_protected: res.day_protected ?? 0, violations: res.violations ?? [] };
        this.weekChanged.emit();
      },
      error: () => { this.applyings[letter] = false; },
    });
  }

  // ── Gradient horaires d'ouverture ─────────────────────────────────────────

  getRowGradient(dayOfWeek: number): string {
    if (dayOfWeek === 6) return '#eef2ff';
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

  // ── AI template generation ────────────────────────────────────────────────

  onTemplateGenerated(templateData: any) {
    const weeks = templateData.weeks ?? {};
    const letters = Object.keys(weeks).filter(l => Array.isArray(weeks[l]) && weeks[l].length > 0) as Letter[];
    if (!letters.length) return;

    from(letters).pipe(
      concatMap(letter => {
        const shifts = weeks[letter].map((s: any) => ({
          collaborator_id: s.collaborator_id,
          day_of_week:     s.day_of_week,
          start_time:      s.start_time.length === 5 ? s.start_time + ':00' : s.start_time,
          end_time:        s.end_time.length === 5   ? s.end_time   + ':00' : s.end_time,
          note:            s.note ?? '',
        }));
        return this.planningService.bulkReplaceTemplateShifts(letter, shifts);
      })
    ).subscribe({
      complete: () => {
        this.showAiPanel = false;
        this.loadAllTemplates();
      }
    });
  }

  // ── Prévisualisation template IA ──────────────────────────────────────────

  openPreview(templateData: any) {
    const letters = Object.keys(templateData.weeks ?? {})
      .filter(l => Array.isArray(templateData.weeks[l]) && templateData.weeks[l].length > 0);
    this.previewTemplate = templateData;
    this.previewLetter   = letters[0] ?? 'A';
  }

  getPreviewLetters(): string[] {
    if (!this.previewTemplate?.weeks) return [];
    return Object.keys(this.previewTemplate.weeks)
      .filter(l => Array.isArray(this.previewTemplate.weeks[l]) && this.previewTemplate.weeks[l].length > 0);
  }

  getPreviewShiftsForDay(letter: string, dayIdx: number): any[] {
    return (this.previewTemplate?.weeks?.[letter] ?? []).filter((s: any) => s.day_of_week === dayIdx);
  }

  getPreviewCollaboratorsForDay(letter: string, dayIdx: number): Collaborator[] {
    const shifts = this.getPreviewShiftsForDay(letter, dayIdx);
    const seen = new Set<number>();
    const result: Collaborator[] = [];
    for (const s of shifts) {
      if (!seen.has(s.collaborator_id)) {
        seen.add(s.collaborator_id);
        const collab = this.team.find(c => c.id === s.collaborator_id);
        if (collab) result.push(collab);
      }
    }
    return result;
  }

  getPreviewShiftsForCollab(letter: string, dayIdx: number, collabId: number): any[] {
    return this.getPreviewShiftsForDay(letter, dayIdx).filter((s: any) => s.collaborator_id === collabId);
  }

  getPreviewShiftLeft(shift: any): number {
    const [h, m] = shift.start_time.split(':').map(Number);
    const minutes = h * 60 + m;
    return Math.max(0, (minutes / (this.totalHours * 60)) * 100);
  }

  getPreviewShiftWidth(shift: any): number {
    const [sh, sm] = shift.start_time.split(':').map(Number);
    const [eh, em] = shift.end_time.split(':').map(Number);
    const duration = (eh * 60 + em) - (sh * 60 + sm);
    const left = this.getPreviewShiftLeft(shift);
    return Math.min(100 - left, (duration / (this.totalHours * 60)) * 100);
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  formatTime(timeStr: string): string { return timeStr.substring(0, 5); }
}
