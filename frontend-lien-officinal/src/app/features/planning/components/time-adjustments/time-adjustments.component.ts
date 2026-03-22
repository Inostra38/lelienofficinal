import { Component, Input, Output, EventEmitter, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PlanningService, TimeAdjustment, WeekResponse } from '../../../../core/services/planning.service';
import { CollaboratorService, Collaborator } from '../../../../core/services/collaborator.service';
import { DatePickerDirective } from '../../../../shared/directives/date-picker.directive';
import { getCollaboratorColor } from '../../../../core/utils/collaborator-colors';

@Component({
  selector: 'app-time-adjustments',
  standalone: true,
  imports: [CommonModule, FormsModule, DatePickerDirective],
  templateUrl: './time-adjustments.component.html',
})
export class TimeAdjustmentsComponent implements OnInit {
  @Input() isManager = false;
  @Input() weekStr   = '';
  @Input() weekData: WeekResponse | null = null;
  @Input() activeCollaboratorId: number | null = null;

  @Output() closed = new EventEmitter<void>();
  @Output() weekChanged = new EventEmitter<void>();

  private planningService     = inject(PlanningService);
  private collaboratorService = inject(CollaboratorService);

  adjustments: TimeAdjustment[] = [];
  team: Collaborator[]          = [];
  loading   = false;
  activeTab: 'list' | 'create' = 'list';

  form = {
    collaborator_id: undefined as number | undefined,
    date: '',
    type: 'overtime' as 'overtime' | 'early_departure',
    actual_time: '',
    reference_time: '',
    duration_minutes: 0,
    shift_id: null as number | null,
    note: '',
  };
  submitting    = false;
  errorMessage  = '';

  readonly TYPES = [
    { value: 'overtime',        label: 'Heures supplémentaires' },
    { value: 'early_departure', label: 'Départ anticipé' },
  ];

ngOnInit() {
    this.loadAdjustments();
    if (this.isManager) {
      this.collaboratorService.getTeam().subscribe(team => {
        this.team = team;
        if (team.length > 0) {
          this.form.collaborator_id = team[0].id;
        }
      });
    }
  }

  loadAdjustments() {
    this.loading = true;
    this.planningService.getAdjustments(this.weekStr).subscribe({
      next:  data => { this.adjustments = data; this.loading = false; },
      error: ()   => { this.loading = false; },
    });
  }

  /** Quand la date ou le collaborateur change, pré-remplir reference_time depuis le shift */
  onDateOrCollabChange() {
    this.form.reference_time = '';
    this.form.shift_id = null;
    this.form.duration_minutes = 0;

    const collabId = this.isManager ? this.form.collaborator_id : this.activeCollaboratorId;
    if (!collabId || !this.form.date || !this.weekData) return;

    const shifts = this.weekData.shifts.filter(s =>
      s.collaborator?.id === collabId && s.start_datetime.startsWith(this.form.date)
    );
    if (shifts.length > 0) {
      const shift = shifts[0];
      this.form.shift_id = shift.id;
      this.form.reference_time = shift.end_datetime.substring(11, 16);
    }
  }

  onActualTimeChange() {
    if (!this.form.actual_time || !this.form.reference_time) return;
    const [refH, refM]    = this.form.reference_time.split(':').map(Number);
    const [actH, actM]    = this.form.actual_time.split(':').map(Number);
    const refMins = refH * 60 + refM;
    const actMins = actH * 60 + actM;

    if (this.form.type === 'overtime') {
      this.form.duration_minutes = Math.max(0, actMins - refMins);
    } else {
      this.form.duration_minutes = Math.max(0, refMins - actMins);
    }
  }

  submit() {
    if (!this.form.date || !this.form.actual_time) {
      this.errorMessage = 'Date et heure réelle obligatoires.';
      return;
    }
    if (this.form.duration_minutes <= 0) {
      this.errorMessage = 'La durée calculée doit être positive.';
      return;
    }

    const collabId = this.isManager ? this.form.collaborator_id : this.activeCollaboratorId;
    this.submitting   = true;
    this.errorMessage = '';

    const payload: any = {
      collaborator_id:  collabId,
      date:             this.form.date,
      type:             this.form.type,
      actual_time:      this.form.actual_time + ':00',
      reference_time:   this.form.reference_time ? this.form.reference_time + ':00' : '00:00:00',
      duration_minutes: this.form.duration_minutes,
      note:             this.form.note,
    };
    if (this.form.shift_id) payload.shift = this.form.shift_id;

    this.planningService.createAdjustment(payload).subscribe({
      next: () => {
        this.submitting = false;
        this.form = {
          collaborator_id: this.isManager && this.team.length > 0 ? this.team[0].id : undefined,
          date: '', type: 'overtime', actual_time: '', reference_time: '',
          duration_minutes: 0, shift_id: null, note: '',
        };
        this.activeTab = 'list';
        this.loadAdjustments();
        this.weekChanged.emit();
      },
      error: (err) => {
        this.errorMessage = err?.error?.detail ?? 'Erreur lors de la création.';
        this.submitting   = false;
      },
    });
  }

  delete(id: number) {
    this.planningService.deleteAdjustment(id).subscribe(() => {
      this.loadAdjustments();
      this.weekChanged.emit();
    });
  }

  formatDuration(minutes: number): string {
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    if (h > 0 && m > 0) return `${h}h${String(m).padStart(2, '0')}`;
    if (h > 0) return `${h}h`;
    return `${m}min`;
  }

  formatDate(iso: string): string {
    return new Date(iso + 'T00:00:00').toLocaleDateString('fr-FR', {
      weekday: 'short', day: 'numeric', month: 'short',
    });
  }

  getInitials(c: { first_name: string; last_name: string }): string {
    return `${c.first_name.charAt(0)}${c.last_name.charAt(0)}`.toUpperCase();
  }

  getAvatarBg(color: string): string {
    return getCollaboratorColor(color).base;
  }

  getTypeLabel(type: string): string {
    return type === 'overtime' ? 'Heures sup.' : 'Départ anticipé';
  }

}
