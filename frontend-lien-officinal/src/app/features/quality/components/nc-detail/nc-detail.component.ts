import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule, FormBuilder, Validators } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { QualityNcService } from '../../services/quality-nc.service';
import { CollaboratorService, Collaborator } from '../../../../core/services/collaborator.service';
import { NonConformity, CorrectiveAction } from '../../models/nonconformity.model';
import { AuthService } from '../../../../core/auth/auth.service';
import { AiService, CorrectiveActionSuggestion } from '../../../../core/services/ai.service';
import { ConfirmService } from '../../../../core/services/confirm.service';
import { DatePickerDirective } from '../../../../shared/directives/date-picker.directive';

@Component({
  selector: 'app-nc-detail',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, FormsModule, RouterLink, DatePickerDirective],
  templateUrl: './nc-detail.component.html',
})
export class NcDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private ncService = inject(QualityNcService);
  private collaboratorService = inject(CollaboratorService);
  private authService = inject(AuthService);
  private fb = inject(FormBuilder);
  private aiService = inject(AiService);
  private confirmService = inject(ConfirmService);

  nc: NonConformity | null = null;
  loading = true;
  error = '';
  collaborators: Collaborator[] = [];
  showAssignSelect = false;
  showCloseForm = false;
  assignedToId: number | null = null;
  resolutionText = '';
  suggestingActions = false;
  aiSuggestions: CorrectiveActionSuggestion[] = [];
  aiSuggestError = '';

  actionForm = this.fb.group({
    description: ['', Validators.required],
    responsible: [null as number | null],
    due_date: [null as string | null],
  });

  ngOnInit() {
    const id = +(this.route.snapshot.paramMap.get('id') || 0);
    this.load(id);
    this.collaboratorService.getTeam().subscribe({ next: (t) => { this.collaborators = t; } });
  }

  load(id: number) {
    this.loading = true;
    this.ncService.getNonConformity(id).subscribe({
      next: (nc) => { this.nc = nc; this.loading = false; },
      error: () => { this.error = 'Non-conformité introuvable.'; this.loading = false; },
    });
  }

  assign() {
    if (!this.nc || !this.assignedToId) return;
    this.ncService.assignNonConformity(this.nc.id, this.assignedToId).subscribe({
      next: (nc) => { this.nc = nc; this.showAssignSelect = false; this.assignedToId = null; },
    });
  }

  close() {
    if (!this.nc) return;
    this.ncService.closeNonConformity(this.nc.id, this.resolutionText).subscribe({
      next: (nc) => { this.nc = nc; this.showCloseForm = false; this.resolutionText = ''; },
    });
  }

  async reopen() {
    if (!this.nc) return;
    if (!await this.confirmService.ask({ title: 'Réouvrir la non-conformité', message: `Confirmer la réouverture de cette non-conformité ?`, danger: false })) return;
    this.ncService.reopenNonConformity(this.nc.id).subscribe({
      next: (nc) => { this.nc = nc; },
    });
  }

  addAction() {
    if (this.actionForm.invalid || !this.nc) { this.actionForm.markAllAsTouched(); return; }
    this.ncService.createCorrectiveAction({
      nonconformity: this.nc.id,
      description: this.actionForm.value.description!,
      responsible: this.actionForm.value.responsible || undefined,
      due_date: this.actionForm.value.due_date || undefined,
    }).subscribe({
      next: (a) => {
        this.nc!.corrective_actions = [...(this.nc!.corrective_actions || []), a];
        this.actionForm.reset();
      },
    });
  }

  markCompleted(action: CorrectiveAction) {
    this.ncService.updateCorrectiveAction(action.id, { completed_at: new Date().toISOString() }).subscribe({
      next: (updated) => {
        this.nc!.corrective_actions = this.nc!.corrective_actions!.map(a => a.id === updated.id ? updated : a);
      },
    });
  }

  suggestActions() {
    if (!this.nc) return;
    this.suggestingActions = true;
    this.aiSuggestError = '';
    this.aiSuggestions = [];
    this.aiService.suggestCorrectiveActions({
      nc_title: this.nc.title,
      nc_description: this.nc.description,
      severity: this.nc.severity,
    }).subscribe({
      next: (res) => {
        this.aiSuggestions = res.actions;
        this.suggestingActions = false;
      },
      error: (err: any) => {
        this.aiSuggestError = err?.error?.error || 'Erreur lors de la génération IA.';
        this.suggestingActions = false;
      },
    });
  }

  applyAiSuggestion(suggestion: CorrectiveActionSuggestion) {
    this.actionForm.patchValue({ description: suggestion.description });
    this.aiSuggestions = [];
  }

  severityLabel(s: string): string {
    return ({ minor: 'Mineur', major: 'Majeur', critical: 'Critique' } as Record<string, string>)[s] || s;
  }

  severityClass(s: string): string {
    return ({
      minor: 'bg-blue-50 text-blue-700 border border-blue-200',
      major: 'bg-amber-50 text-amber-700 border border-amber-200',
      critical: 'bg-red-50 text-red-700 border border-red-200',
    } as Record<string, string>)[s] || '';
  }

  statusLabel(s: string): string {
    return ({ open: 'Ouvert', in_progress: 'En cours', closed: 'Clôturé' } as Record<string, string>)[s] || s;
  }

  statusClass(s: string): string {
    return ({
      open: 'bg-orange-50 text-orange-700 border border-orange-200',
      in_progress: 'bg-blue-50 text-blue-700 border border-blue-200',
      closed: 'bg-gray-50 text-gray-500 border border-gray-200',
    } as Record<string, string>)[s] || '';
  }
}
