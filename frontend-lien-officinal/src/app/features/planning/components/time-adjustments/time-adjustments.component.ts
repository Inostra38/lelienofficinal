import { Component, Input, Output, EventEmitter, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PlanningService, TimeAdjustment, WeekResponse, AbsenceRequest } from '../../../../core/services/planning.service';
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
  @Input() set initialTab(tab: 'list' | 'create' | 'absence') { this.activeTab = tab; }
  @Input() mode: 'adjustments' | 'absence' = 'adjustments';

  @Output() closed = new EventEmitter<void>();
  @Output() weekChanged = new EventEmitter<void>();

  private planningService     = inject(PlanningService);
  private collaboratorService = inject(CollaboratorService);

  adjustments: TimeAdjustment[]   = [];
  absenceRequests: AbsenceRequest[] = [];
  team: Collaborator[]            = [];
  loading                = false;
  absenceRequestsLoading = false;
  activeTab: 'list' | 'create' | 'absence' = 'list';

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
  absenceForm = {
    collaborator_id: undefined as number | undefined,
    start_date: '',
    end_date: '',
    type: 'cp' as 'cp' | 'maladie' | 'rcr' | 'sans_solde' | 'conge_exceptionnel',
    note: '',
  };
  submitting    = false;
  errorMessage  = '';

  readonly TYPES = [
    { value: 'overtime',        label: 'Heures supplémentaires' },
    { value: 'early_departure', label: 'Départ anticipé' },
  ];

  readonly ABSENCE_TYPES = [
    { value: 'cp',         label: 'Congés payés' },
    { value: 'maladie',    label: 'Maladie' },
    { value: 'rcr',        label: 'RCR' },
    { value: 'sans_solde', label: 'Sans solde' },
    { value: 'conge_exceptionnel', label: 'Congé exceptionnel légal' },
  ];

ngOnInit() {
    if (this.mode === 'absence') {
      this.loadAbsenceRequests();
    } else {
      this.loadAdjustments();
    }
    if (this.isManager) {
      this.collaboratorService.getTeam().subscribe(team => {
        this.team = team;
        if (team.length > 0) {
          this.form.collaborator_id        = team[0].id;
          this.absenceForm.collaborator_id = team[0].id;
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

  loadAbsenceRequests() {
    this.absenceRequestsLoading = true;
    this.planningService.getAbsences().subscribe({
      next:  data => { this.absenceRequests = data; this.absenceRequestsLoading = false; },
      error: ()   => { this.absenceRequestsLoading = false; },
    });
  }

  approveAbsence(id: number) {
    this.planningService.approveAbsence(id).subscribe(() => this.loadAbsenceRequests());
  }

  rejectAbsence(id: number) {
    this.planningService.rejectAbsence(id).subscribe(() => this.loadAbsenceRequests());
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

  getAbsenceTypeLabel(type: string): string {
    return this.ABSENCE_TYPES.find(t => t.value === type)?.label ?? type;
  }

  readonly STATUS_LABELS: Record<string, string> = {
    pending:  'En attente',
    approved: 'Approuvée',
    rejected: 'Refusée',
  };

  readonly STATUS_CLASSES: Record<string, string> = {
    pending:  'bg-amber-100 text-amber-700',
    approved: 'bg-green-100 text-green-700',
    rejected: 'bg-red-100 text-red-700',
  };

  submitAbsence() {
    if (!this.absenceForm.start_date || !this.absenceForm.end_date) {
      this.errorMessage = 'Dates de début et de fin obligatoires.';
      return;
    }
    const collabId = this.isManager ? this.absenceForm.collaborator_id : this.activeCollaboratorId;
    if (!collabId) { this.errorMessage = 'Collaborateur obligatoire.'; return; }

    this.submitting   = true;
    this.errorMessage = '';
    this.planningService.createAbsence({
      collaborator_id: collabId,
      start_date: this.absenceForm.start_date,
      end_date:   this.absenceForm.end_date,
      type:       this.absenceForm.type,
      note:       this.absenceForm.note,
    }).subscribe({
      next: () => {
        this.submitting = false;
        this.absenceForm = {
          collaborator_id: this.isManager && this.team.length > 0 ? this.team[0].id : undefined,
          start_date: '', end_date: '', type: 'cp', note: '',
        };
        this.activeTab = 'list';
        this.weekChanged.emit();
      },
      error: (err) => {
        this.errorMessage = err?.error?.detail ?? 'Erreur lors de la création.';
        this.submitting   = false;
      },
    });
  }

}
