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

  // ── Feedback jours ouvrés CP (calcul côté client) ──────────────────────────

  /** Retourne { workingDays, ferieCount } pour la plage CP sélectionnée. */
  get cpWorkingDaysFeedback(): { workingDays: number; ferieCount: number } | null {
    if (this.form.type !== 'cp' || !this.form.start_date || !this.form.end_date) return null;
    if (this.form.start_date > this.form.end_date) return null;
    const start = new Date(this.form.start_date + 'T00:00:00');
    const end   = new Date(this.form.end_date   + 'T00:00:00');
    const years = new Set<number>();
    for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) years.add(d.getFullYear());
    const feries = new Set<string>();
    for (const y of years) {
      for (const f of this._getJoursFeries(y)) feries.add(this._isoDate(f));
    }
    let workingDays = 0, ferieCount = 0;
    for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
      if (d.getDay() === 0) continue; // dimanche
      const iso = this._isoDate(d);
      if (feries.has(iso)) { ferieCount++; continue; }
      workingDays++;
    }
    return { workingDays, ferieCount };
  }

  private _isoDate(d: Date): string {
    const p = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
  }

  private _getJoursFeries(year: number): Date[] {
    const a = year % 19, b = Math.floor(year / 100), c = year % 100;
    const d = Math.floor(b / 4), e = b % 4, f = Math.floor((b + 8) / 25);
    const g = Math.floor((b - f + 1) / 3), h = (19 * a + b - d - g + 15) % 30;
    const ii = Math.floor(c / 4), k = c % 4, l = (32 + 2 * e + 2 * ii - h - k) % 7;
    const m = Math.floor((a + 11 * h + 22 * l) / 451);
    const eMonth = Math.floor((h + l - 7 * m + 114) / 31);
    const eDay   = ((h + l - 7 * m + 114) % 31) + 1;
    const add = (n: number) => new Date(year, eMonth - 1, eDay + n);
    return [
      new Date(year, 0, 1), add(1), new Date(year, 4, 1), new Date(year, 4, 8),
      add(39), add(50), new Date(year, 6, 14), new Date(year, 7, 15),
      new Date(year, 10, 1), new Date(year, 10, 11), new Date(year, 11, 25),
    ];
  }

}
