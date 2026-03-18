import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { QualityService } from '../../services/quality.service';
import { Procedure, ProcedureAttachment, ProcedureImage } from '../../models/procedure.model';
import { CollaboratorService, Collaborator } from '../../../../core/services/collaborator.service';
import { AiService } from '../../../../core/services/ai.service';

@Component({
  selector: 'app-procedure-editor',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './procedure-editor.component.html',
})
export class ProcedureEditorComponent implements OnInit {
  private fb = inject(FormBuilder);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private qualityService = inject(QualityService);
  private collaboratorService = inject(CollaboratorService);
  private aiService = inject(AiService);

  procedureId: number | null = null;
  groupId: number | null = null;
  isEditMode = false;
  loading = false;
  saving = false;
  generating = false;
  error = '';
  aiError = '';

  procedure: Procedure | null = null;
  procedures: Procedure[] = [];
  collaborators: Collaborator[] = [];
  selectedPilotIds: number[] = [];
  attachments: ProcedureAttachment[] = [];
  images: ProcedureImage[] = [];

  form = this.fb.group({
    is_group: [false],
    title: ['', Validators.required],
    reference: ['', Validators.required],
    category: ['', Validators.required],
    parent: [null as number | null],
    content: [''],
  });

  get isGroup(): boolean {
    return this.form.get('is_group')?.value ?? false;
  }

  readonly categories = [
    { value: 'dispensation', label: 'Dispensation' },
    { value: 'hygiene', label: 'Hygiène' },
    { value: 'stock', label: 'Stock' },
    { value: 'administratif', label: 'Administratif' },
    { value: 'autre', label: 'Autre' },
  ];

  ngOnInit() {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) { this.procedureId = +id; this.isEditMode = true; }
    const groupParam = this.route.snapshot.queryParamMap.get('group');
    if (groupParam) { this.groupId = +groupParam; }
    const folderParam = this.route.snapshot.queryParamMap.get('folder');
    if (folderParam === 'true') { this.form.get('is_group')!.setValue(true); }
    this.collaboratorService.getTeam().subscribe({ next: (t) => { this.collaborators = t; } });
    this.qualityService.getProcedures().subscribe({ next: (p) => { this.procedures = p.filter(x => x.status === 'active' || x.is_group); } });
    if (this.isEditMode && this.procedureId) { this.loadProcedure(); }
    this.form.get('is_group')!.valueChanges.subscribe(isGroup => {
      const ref = this.form.get('reference')!;
      if (isGroup) { ref.clearValidators(); ref.setValue(''); }
      else { ref.setValidators(Validators.required); }
      ref.updateValueAndValidity();
    });
  }

  loadProcedure() {
    this.loading = true;
    this.qualityService.getProcedure(this.procedureId!).subscribe({
      next: (p) => {
        this.procedure = p;
        this.attachments = p.attachments || [];
        this.images = p.images || [];
        this.form.patchValue({
          is_group: p.is_group ?? false,
          title: p.title,
          reference: p.reference ?? '',
          category: p.category,
          parent: p.parent ?? null,
          content: p.content || '',
        });
        if (p.is_group) {
          const ref = this.form.get('reference')!;
          ref.clearValidators();
          ref.updateValueAndValidity();
        }
        this.selectedPilotIds = p.pilots?.map(c => c.id) ?? [];
        this.loading = false;
      },
      error: () => { this.error = 'Erreur lors du chargement.'; this.loading = false; },
    });
  }

  togglePilot(id: number) {
    const idx = this.selectedPilotIds.indexOf(id);
    if (idx === -1) { this.selectedPilotIds = [...this.selectedPilotIds, id]; }
    else { this.selectedPilotIds = this.selectedPilotIds.filter(x => x !== id); }
  }

  isPilotSelected(id: number): boolean {
    return this.selectedPilotIds.includes(id);
  }

  save(publish = false) {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    this.saving = true;
    const payload: any = {
      is_group: this.form.value.is_group,
      title: this.form.value.title!,
      reference: this.isGroup ? null : (this.form.value.reference || null),
      category: this.form.value.category,
      content: this.form.value.content || '',
      pilot_ids: this.selectedPilotIds,
      parent: this.form.value.parent,
      group: this.groupId ?? (this.procedure?.group ?? null),
    };
    const obs$ = this.isEditMode
      ? this.qualityService.updateProcedure(this.procedureId!, payload)
      : this.qualityService.createProcedure(payload);
    obs$.subscribe({
      next: (saved) => {
        if (publish) {
          this.qualityService.publishProcedure(saved.id).subscribe({
            next: () => this.router.navigate(['/quality/procedures', saved.id]),
            error: () => { this.saving = false; this.error = 'Erreur lors de la publication.'; },
          });
        } else {
          this.saving = false;
          this.router.navigate(['/quality/procedures', saved.id]);
        }
      },
      error: (err: any) => {
        this.saving = false;
        console.error('SAVE ERROR body:', JSON.stringify(err?.error));
        const detail = err?.error?.detail || err?.error?.non_field_errors?.[0]
          || JSON.stringify(err?.error || 'Erreur inconnue');
        this.error = `Erreur (${err?.status}) : ${detail}`;
      },
    });
  }

  onImageSelected(event: Event) {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (!file || !this.procedureId) return;
    this.qualityService.uploadImage(this.procedureId, file).subscribe({
      next: (img) => { this.images = [...this.images, img]; },
    });
  }

  onAttachmentSelected(event: Event) {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (!file || !this.procedureId) return;
    const name = prompt('Nom d\'affichage de la pièce jointe :', file.name) || file.name;
    this.qualityService.uploadAttachment(this.procedureId, file, name).subscribe({
      next: (a) => { this.attachments = [...this.attachments, a]; },
    });
  }

  deleteAttachment(id: number) {
    if (!confirm('Supprimer cette pièce jointe ?')) return;
    this.qualityService.deleteAttachment(id).subscribe({
      next: () => { this.attachments = this.attachments.filter(a => a.id !== id); },
    });
  }

  generateContent() {
    const title = this.form.value.title?.trim();
    const category = this.form.value.category?.trim();
    const reference = this.form.value.reference?.trim() || '';
    if (!title || !category) return;
    this.generating = true;
    this.aiError = '';
    this.aiService.generateProcedureContent({ title, category, reference }).subscribe({
      next: (res) => {
        this.form.patchValue({ content: res.content });
        this.generating = false;
      },
      error: (err: any) => {
        this.aiError = err?.error?.error || 'Erreur lors de la génération IA.';
        this.generating = false;
      },
    });
  }

  cancel() {
    this.router.navigate(['/quality']);
  }
}
