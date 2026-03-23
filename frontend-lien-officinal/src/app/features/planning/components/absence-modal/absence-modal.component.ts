import { Component, Input, Output, EventEmitter, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  PlanningService,
  AbsenceRequest,
  CreateAbsenceDto,
} from '../../../../core/services/planning.service';
import { CollaboratorService, Collaborator } from '../../../../core/services/collaborator.service';
import { DatePickerDirective } from '../../../../shared/directives/date-picker.directive';

@Component({
  selector: 'app-absence-modal',
  standalone: true,
  imports: [CommonModule, FormsModule, DatePickerDirective],
  templateUrl: './absence-modal.component.html',
})
export class AbsenceModalComponent implements OnInit {
  /** Mode staff : créer sa propre demande. Mode manager : voir + gérer toutes. */
  @Input() isManager = false;
  @Input() weekStr   = '';

  @Output() closed = new EventEmitter<void>();

  private planningService     = inject(PlanningService);
  private collaboratorService = inject(CollaboratorService);

  // ── Liste des absences ────────────────────────────────────────────────────
  absences: AbsenceRequest[] = [];
  team: Collaborator[]       = [];
  loading    = false;
  activeTab: 'list' | 'create' = 'list';

  // ── Formulaire création ───────────────────────────────────────────────────
  form: CreateAbsenceDto & { collaborator_id?: number } = {
    collaborator_id: undefined,
    start_date: '',
    end_date:   '',
    type:       'cp',
    note:       '',
  };
  submitting      = false;
  errorMessage    = '';
  successMessage  = '';

  private readonly ALL_TYPES = [
    { value: 'cp',                 label: 'Congés payés' },
    { value: 'conge_exceptionnel', label: 'Congé exceptionnel légal' },
    { value: 'maladie',            label: 'Maladie' },
    { value: 'rcr',                label: 'RCR' },
    { value: 'sans_solde',         label: 'Sans solde' },
  ];

  /** Types disponibles selon le rôle.
   *  Salarié : CP · Congé exceptionnel · Sans solde
   *  Manager : tous */
  get TYPES() {
    return this.isManager
      ? this.ALL_TYPES
      : this.ALL_TYPES.filter(t =>
          t.value === 'cp' || t.value === 'conge_exceptionnel' || t.value === 'rcr' || t.value === 'sans_solde'
        );
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

  ngOnInit() {
    this.loadAbsences();
    if (this.isManager) {
      this.collaboratorService.getTeam().subscribe(team => {
        this.team = team;
        if (team.length > 0) {
          this.form.collaborator_id = team[0].id;
        }
      });
    }
  }

  loadAbsences() {
    this.loading = true;
    this.planningService.getAbsences().subscribe({
      next:  data => { this.absences = data; this.loading = false; },
      error: ()   => { this.loading = false; },
    });
  }

  // ── Création ──────────────────────────────────────────────────────────────

  submit() {
    if (!this.form.start_date || !this.form.end_date) {
      this.errorMessage = 'Les dates de début et de fin sont obligatoires.';
      return;
    }
    if (this.form.start_date > this.form.end_date) {
      this.errorMessage = 'La date de début doit être avant la date de fin.';
      return;
    }
    if (this.isManager && !this.form.collaborator_id) {
      this.errorMessage = 'Veuillez sélectionner un collaborateur.';
      return;
    }

    this.submitting     = true;
    this.errorMessage   = '';
    this.successMessage = '';

    this.planningService.createAbsence(this.form).subscribe({
      next: (res) => {
        this.submitting = false;
        this.form = {
          collaborator_id: this.isManager && this.team.length > 0 ? this.team[0].id : undefined,
          start_date: '', end_date: '', type: 'cp', note: '',
        };
        if (res.skipped_days > 0) {
          const s = res.skipped_days > 1 ? 's' : '';
          this.successMessage = `${res.absences.length > 1 ? res.absences.length + ' tranche(s) créée(s)' : 'Absence créée'}. ${res.skipped_days} jour${s} exclu${s} (dimanche, férié ou jour fermé).`;
          this.activeTab = 'list';
        } else {
          this.activeTab = 'list';
        }
        this.loadAbsences();
      },
      error: (err) => {
        this.errorMessage = err?.error?.detail ?? 'Erreur lors de la création de la demande.';
        this.submitting   = false;
      },
    });
  }

  // ── Gestion manager ───────────────────────────────────────────────────────

  approve(id: number) {
    this.planningService.approveAbsence(id).subscribe(() => this.loadAbsences());
  }

  reject(id: number) {
    this.planningService.rejectAbsence(id).subscribe(() => this.loadAbsences());
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  getTypeLabel(type: string): string {
    return this.ALL_TYPES.find(t => t.value === type)?.label ?? type;
  }

  formatDate(iso: string): string {
    return new Date(iso + 'T00:00:00').toLocaleDateString('fr-FR', {
      day: 'numeric', month: 'short', year: 'numeric',
    });
  }

  getInitials(collab: { first_name: string; last_name: string }): string {
    return `${collab.first_name.charAt(0)}${collab.last_name.charAt(0)}`.toUpperCase();
  }

}
