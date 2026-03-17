import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { QualityService } from '../../services/quality.service';
import { Procedure, ProcedureAttachment, ProcedureImage } from '../../models/procedure.model';
import { CollaboratorService, Collaborator } from '../../../../core/services/collaborator.service';

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

  procedureId: number | null = null;
  isEditMode = false;
  loading = false;
  saving = false;
  error = '';

  procedure: Procedure | null = null;
  procedures: Procedure[] = [];
  collaborators: Collaborator[] = [];
  attachments: ProcedureAttachment[] = [];
  images: ProcedureImage[] = [];

  form = this.fb.group({
    title: ['', Validators.required],
    reference: ['', Validators.required],
    category: ['', Validators.required],
    pilot: [null as number | null],
    parent: [null as number | null],
    content: [''],
  });

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
    this.collaboratorService.getTeam().subscribe({ next: (t) => { this.collaborators = t; } });
    this.qualityService.getProcedures().subscribe({ next: (p) => { this.procedures = p.filter(x => x.status === 'active'); } });
    if (this.isEditMode && this.procedureId) { this.loadProcedure(); }
  }

  loadProcedure() {
    this.loading = true;
    this.qualityService.getProcedure(this.procedureId!).subscribe({
      next: (p) => {
        this.procedure = p;
        this.attachments = p.attachments || [];
        this.images = p.images || [];
        this.form.patchValue({
          title: p.title,
          reference: p.reference,
          category: p.category,
          pilot: p.pilot?.id ?? null,
          parent: p.parent ?? null,
          content: p.content || '',
        });
        this.loading = false;
      },
      error: () => { this.error = 'Erreur lors du chargement.'; this.loading = false; },
    });
  }

  save(publish = false) {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    this.saving = true;
    const payload: Partial<Procedure> = {
      title: this.form.value.title!,
      reference: this.form.value.reference!,
      category: this.form.value.category as any,
      content: this.form.value.content || '',
      pilot: this.form.value.pilot as any,
      parent: this.form.value.parent as any,
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
      error: () => { this.saving = false; this.error = 'Erreur lors de la sauvegarde.'; },
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

  cancel() { this.router.navigate(['/quality/procedures']); }
}
