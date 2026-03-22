import { Component, OnInit, Input, Output, EventEmitter, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PlanningService } from '../../../../core/services/planning.service';

export interface ShiftFormCollab {
  id: number;
  full_name: string;
  color: string;
}

@Component({
  selector: 'app-shift-form',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './shift-form.component.html',
})
export class ShiftFormComponent implements OnInit {
  private planningService = inject(PlanningService);

  @Input() collaborators: ShiftFormCollab[] = [];
  @Input() weekDays: Date[] = [];
  @Input() prefilledCollaboratorId: number | null = null;
  @Input() prefilledDate = '';

  @Output() saved  = new EventEmitter<void>();
  @Output() closed = new EventEmitter<void>();

  form = {
    collaborator_id: 0,
    date:            '',
    start_time:      '09:00',
    end_time:        '19:00',
    is_extra_hour:   false,
    note:            '',
  };

  submitting = false;
  errorMsg   = '';

  ngOnInit() {
    this.form.collaborator_id = this.prefilledCollaboratorId ?? (this.collaborators[0]?.id ?? 0);
    this.form.date            = this.prefilledDate || this.getDayIso(this.weekDays[0]);
  }

  readonly hoursArr = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, '0'));
  readonly minsArr  = ['00','05','10','15','20','25','30','35','40','45','50','55'];

  getH(field: 'start_time' | 'end_time'): string { return (this.form[field] || '00:00').split(':')[0]; }
  getM(field: 'start_time' | 'end_time'): string { return (this.form[field] || '00:00').split(':')[1]; }
  setH(field: 'start_time' | 'end_time', v: string) { this.form[field] = `${v}:${this.getM(field)}`; }
  setM(field: 'start_time' | 'end_time', v: string) { this.form[field] = `${this.getH(field)}:${v}`; }

  /** Vrai si le shift se termine le lendemain (fin < début) */
  get crossesMidnight(): boolean {
    return this.form.end_time < this.form.start_time;
  }

  private nextDayIso(iso: string): string {
    const d = new Date(iso + 'T00:00:00');
    d.setDate(d.getDate() + 1);
    const p = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
  }

  getDayIso(d: Date): string {
    const p = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
  }

  getDayLabel(d: Date): string {
    return d.toLocaleDateString('fr-FR', { weekday: 'short', day: 'numeric', month: 'short' });
  }

  submit() {
    this.errorMsg = '';

    if (!this.form.collaborator_id || !this.form.date) {
      this.errorMsg = 'Veuillez renseigner tous les champs obligatoires.';
      return;
    }

    const start_datetime = `${this.form.date}T${this.form.start_time}:00`;
    const end_date       = this.crossesMidnight ? this.nextDayIso(this.form.date) : this.form.date;
    const end_datetime   = `${end_date}T${this.form.end_time}:00`;

    this.submitting = true;
    this.planningService.createShift({
      collaborator_id: this.form.collaborator_id,
      start_datetime,
      end_datetime,
      is_extra_hour: this.form.is_extra_hour,
      note:          this.form.note,
    }).subscribe({
      next:  () => { this.submitting = false; this.saved.emit(); },
      error: () => { this.submitting = false; this.errorMsg = 'Erreur lors de la création.'; },
    });
  }
}
