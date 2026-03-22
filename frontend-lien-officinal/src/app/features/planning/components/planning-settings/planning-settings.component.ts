import { Component, OnInit, Output, EventEmitter, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { forkJoin } from 'rxjs';
import { CdkDragDrop, DragDropModule, moveItemInArray } from '@angular/cdk/drag-drop';

import { PlanningService, PlanningSettings, OpeningHours } from '../../../../core/services/planning.service';
import { CollaboratorService, Collaborator } from '../../../../core/services/collaborator.service';
import { getCollaboratorColor } from '../../../../core/utils/collaborator-colors';

interface CollabOrder {
  id: number;
  first_name: string;
  last_name: string;
  role: string;
  color: string;
}

interface DayRow {
  dayIndex: number;
  label:    string;
  slots:    OpeningHours[];
  addForm:  { start_time: string; end_time: string } | null;
  addError: string;
}

@Component({
  selector: 'app-planning-settings',
  standalone: true,
  imports: [CommonModule, FormsModule, DragDropModule],
  templateUrl: './planning-settings.component.html',
})
export class PlanningSettingsComponent implements OnInit {
  private planningService     = inject(PlanningService);
  private collaboratorService = inject(CollaboratorService);

  @Output() closed = new EventEmitter<void>();

  activeTab: 'horaires' | 'equipe' | 'gardes' = 'horaires';

  settings: PlanningSettings = {
    draft_window: 2,
    on_call_day_start:   null,
    on_call_day_end:     null,
    on_call_night_start: null,
    on_call_night_end:   null,
    on_call_sunday: false,
  };

  collaborators: CollabOrder[] = [];

  days: DayRow[] = [
    { dayIndex: 0, label: 'Lundi',     slots: [], addForm: null, addError: '' },
    { dayIndex: 1, label: 'Mardi',     slots: [], addForm: null, addError: '' },
    { dayIndex: 2, label: 'Mercredi',  slots: [], addForm: null, addError: '' },
    { dayIndex: 3, label: 'Jeudi',     slots: [], addForm: null, addError: '' },
    { dayIndex: 4, label: 'Vendredi',  slots: [], addForm: null, addError: '' },
    { dayIndex: 5, label: 'Samedi',    slots: [], addForm: null, addError: '' },
  ];

  loading    = true;
  saving     = false;
  errorMsg   = '';
  successMsg = '';

  ngOnInit() {
    forkJoin({
      settings:      this.planningService.getSettings(),
      collaborators: this.collaboratorService.getTeam(),
      openingHours:  this.planningService.getOpeningHours(),
    }).subscribe({
      next: ({ settings, collaborators, openingHours }) => {
        this.settings = settings;
        this.collaborators = collaborators
          .filter((c: Collaborator) => c.is_active !== false)
          .map((c: Collaborator) => ({
            id:         c.id!,
            first_name: c.first_name,
            last_name:  c.last_name,
            role:       c.role,
            color:      c.color,
          }));
        this._distributeSlots(openingHours);
        this.loading = false;
      },
      error: () => { this.loading = false; this.errorMsg = 'Erreur de chargement.'; },
    });
  }

  private _distributeSlots(slots: OpeningHours[]) {
    for (const day of this.days) day.slots = [];
    for (const s of slots) {
      const day = this.days.find(d => d.dayIndex === s.day_of_week);
      if (day) day.slots.push(s);
    }
  }

  // ── Gestion créneaux ────────────────────────────────────────────────────────

  openAddForm(day: DayRow) {
    day.addForm  = { start_time: '08:30', end_time: '12:30' };
    day.addError = '';
  }

  cancelAdd(day: DayRow) {
    day.addForm = null;
  }

  confirmAdd(day: DayRow) {
    if (!day.addForm) return;
    const { start_time, end_time } = day.addForm;
    if (end_time <= start_time) { day.addError = 'Fin > début requis.'; return; }
    day.addError = '';
    this.planningService.createOpeningHours({
      day_of_week: day.dayIndex,
      start_time:  start_time + ':00',
      end_time:    end_time   + ':00',
    }).subscribe({
      next: slot => { day.slots.push(slot); day.slots.sort((a, b) => a.start_time.localeCompare(b.start_time)); day.addForm = null; },
      error: () => { day.addError = 'Erreur lors de la création.'; },
    });
  }

  deleteSlot(day: DayRow, slot: OpeningHours) {
    this.planningService.deleteOpeningHours(slot.id).subscribe(() => {
      day.slots = day.slots.filter(s => s.id !== slot.id);
    });
  }

  formatSlot(slot: OpeningHours): string {
    return `${slot.start_time.substring(0, 5)} – ${slot.end_time.substring(0, 5)}`;
  }

  // ── Sauvegarde settings généraux ───────────────────────────────────────────

  saveSettings() {
    this.saving     = true;
    this.errorMsg   = '';
    this.successMsg = '';
    this.planningService.updateSettings(this.settings).subscribe({
      next: () => {
        this.saving = false;
        this.successMsg = 'Paramètres enregistrés.';
        setTimeout(() => { this.successMsg = ''; }, 2500);
      },
      error: () => { this.saving = false; this.errorMsg = 'Erreur lors de l\'enregistrement.'; },
    });
  }

  getAvatarBg(color: string): string { return getCollaboratorColor(color).base; }
  getInitials(c: CollabOrder): string {
    return `${c.first_name.charAt(0)}${c.last_name.charAt(0)}`.toUpperCase();
  }

  // ── Réordonnancement ──────────────────────────────────────────────────────

  onDrop(event: CdkDragDrop<CollabOrder[]>) {
    moveItemInArray(this.collaborators, event.previousIndex, event.currentIndex);
    this.saveOrder();
  }

  moveUp(index: number) {
    if (index === 0) return;
    moveItemInArray(this.collaborators, index, index - 1);
    this.saveOrder();
  }

  moveDown(index: number) {
    if (index === this.collaborators.length - 1) return;
    moveItemInArray(this.collaborators, index, index + 1);
    this.saveOrder();
  }

  private saveOrder() {
    const order = this.collaborators.map(c => c.id);
    this.collaboratorService.reorderCollaborators(order).subscribe();
  }
}
