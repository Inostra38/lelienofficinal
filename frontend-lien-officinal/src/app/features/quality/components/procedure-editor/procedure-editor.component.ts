import { Component, OnInit, ViewChild, inject } from '@angular/core';
import { forkJoin, of } from 'rxjs';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators, FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { QualityService } from '../../services/quality.service';
import { Procedure, ProcedureAttachment, ProcedureImage } from '../../models/procedure.model';
import { CollaboratorService, Collaborator } from '../../../../core/services/collaborator.service';
import { AiService } from '../../../../core/services/ai.service';
import { QuillEditorWrapperComponent, QuillRange } from '../quill-editor-wrapper/quill-editor-wrapper.component';
import { BadgeSelectorComponent } from '../badge-selector/badge-selector.component';
import { AttachmentUploaderComponent } from '../attachment-uploader/attachment-uploader.component';
import { DatePickerDirective } from '../../../../shared/directives/date-picker.directive';

@Component({
  selector: 'app-procedure-editor',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, FormsModule, QuillEditorWrapperComponent, BadgeSelectorComponent, AttachmentUploaderComponent, DatePickerDirective],
  templateUrl: './procedure-editor.component.html',
})
export class ProcedureEditorComponent implements OnInit {
  private fb = inject(FormBuilder);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private qualityService = inject(QualityService);
  private collaboratorService = inject(CollaboratorService);
  private aiService = inject(AiService);

  @ViewChild(QuillEditorWrapperComponent) private quillWrapper?: QuillEditorWrapperComponent;
  @ViewChild(AttachmentUploaderComponent) private uploaderRef?: AttachmentUploaderComponent;

  procedureId: number | null = null;
  groupId: number | null = null;
  isEditMode = false;
  loading = false;
  saving = false;
  refactoring = false;
  error = '';
  refactorError = '';
  quillSelection: QuillRange | null = null;

  procedure: Procedure | null = null;
  collaborators: Collaborator[] = [];
  attachments: ProcedureAttachment[] = [];
  images: ProcedureImage[] = [];
  pendingImages: File[] = [];
  pendingImagePreviews: string[] = [];

  form = this.fb.group({
    title: ['', Validators.required],
    reference: [null as string | null],
    category_ids: [[] as number[]],
    pilot_ids: [[] as number[]],
    content: [''],
    next_review_date: [null as string | null],
  });

  get selectedPilotIds(): number[] {
    return this.form.get('pilot_ids')?.value ?? [];
  }

  ngOnInit() {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) { this.procedureId = +id; this.isEditMode = true; }

    const groupParam = this.route.snapshot.queryParamMap.get('group');
    if (groupParam) { this.groupId = +groupParam; }

    this.collaboratorService.getTeam().subscribe({
      next: (t) => { this.collaborators = t; },
    });

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
          reference: p.reference ?? null,
          category_ids: p.categories?.map(c => c.id) ?? [],
          pilot_ids: p.pilots?.map(c => c.id) ?? [],
          content: p.content || '',
          next_review_date: p.next_review_date ?? null,
        });
        this.loading = false;
      },
      error: () => { this.error = 'Erreur lors du chargement.'; this.loading = false; },
    });
  }

  // ── Pilots ──────────────────────────────────────────────────────────────

  togglePilot(id: number) {
    const current = this.selectedPilotIds;
    const updated = current.includes(id)
      ? current.filter(x => x !== id)
      : [...current, id];
    this.form.get('pilot_ids')!.setValue(updated);
  }

  isPilotSelected(id: number): boolean {
    return this.selectedPilotIds.includes(id);
  }

  getInitials(c: Collaborator): string {
    return ((c.first_name?.[0] ?? '') + (c.last_name?.[0] ?? '')).toUpperCase();
  }

  getAvatarColor(name: string): string {
    const colors = ['#1B5E20', '#0D47A1', '#4A148C', '#E65100', '#880E4F', '#006064', '#37474F'];
    let hash = 0;
    for (let i = 0; i < name.length; i++) {
      hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    return colors[Math.abs(hash) % colors.length];
  }

  // ── Save ────────────────────────────────────────────────────────────────

  openPublishModal() {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    this.publishSummary = '';
    this.showPublishModal = true;
  }

  save(publish = false, changeSummary?: string) {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    this.saving = true;
    const v = this.form.value;
    const payload: any = {
      title: v.title!,
      reference: v.reference || null,
      category_ids: v.category_ids ?? [],
      pilot_ids: v.pilot_ids ?? [],
      content: v.content || '',
      next_review_date: v.next_review_date || null,
      group: this.groupId ?? (this.procedure?.group ?? null),
    };
    const obs$ = this.isEditMode
      ? this.qualityService.updateProcedure(this.procedureId!, payload)
      : this.qualityService.createProcedure(payload);
    obs$.subscribe({
      next: (saved) => {
        const imageUploads$ = this.pendingImages.length > 0
          ? forkJoin(this.pendingImages.map(f => this.qualityService.uploadImage(saved.id, f)))
          : of([]);
        const attachUploads$ = this.uploaderRef
          ? this.uploaderRef.flushPending(saved.id)
          : of([]);

        forkJoin([imageUploads$, attachUploads$]).subscribe({
          next: () => this.afterSave(saved, publish, changeSummary),
          error: () => this.afterSave(saved, publish, changeSummary),
        });
      },
      error: (err: any) => {
        this.saving = false;
        const detail = err?.error?.detail || err?.error?.non_field_errors?.[0]
          || JSON.stringify(err?.error || 'Erreur inconnue');
        this.error = `Erreur (${err?.status}) : ${detail}`;
      },
    });
  }

  // ── Images & Attachments ────────────────────────────────────────────────

  removeImage(img: ProcedureImage) {
    this.qualityService.deleteImage(img.id).subscribe({
      next: () => { this.images = this.images.filter(i => i.id !== img.id); },
    });
  }

  removePendingImage(index: number) {
    this.pendingImages = this.pendingImages.filter((_, i) => i !== index);
    this.pendingImagePreviews = this.pendingImagePreviews.filter((_, i) => i !== index);
  }

  onImageSelected(event: Event) {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (!file) return;
    (event.target as HTMLInputElement).value = '';

    if (!this.procedureId) {
      // Mode création : mise en attente avec prévisualisation
      const reader = new FileReader();
      reader.onload = (e) => {
        this.pendingImagePreviews = [...this.pendingImagePreviews, e.target?.result as string];
      };
      reader.readAsDataURL(file);
      this.pendingImages = [...this.pendingImages, file];
      return;
    }

    this.qualityService.uploadImage(this.procedureId, file).subscribe({
      next: (img) => { this.images = [...this.images, img]; },
    });
  }

  // ── IA ──────────────────────────────────────────────────────────────────

  showConfirmModal = false;
  private savedRange: QuillRange | null = null;

  // ── Modale publication ───────────────────────────────────────────────────
  showPublishModal = false;
  publishSummary = '';

  onQuillSelectionChange(range: QuillRange | null): void {
    this.quillSelection = range;
  }

  openRefactorConfirm(): void {
    if (!this.quillSelection) return;
    // Sauvegarder la range avant que la modale ne fasse perdre le focus
    this.savedRange = this.quillSelection;
    this.showConfirmModal = true;
  }

  cancelRefactor(): void {
    this.showConfirmModal = false;
    this.savedRange = null;
  }

  refactorSelection(): void {
    this.showConfirmModal = false;
    if (!this.savedRange || !this.quillWrapper) return;

    const selectedText = this.quillWrapper.getSelectedText();
    if (!selectedText) return;

    this.refactoring = true;
    this.refactorError = '';

    this.aiService.refactorText({ text: selectedText, mode: 'selection' }).subscribe({
      next: (res) => {
        this.quillWrapper!.replaceSelection(res.result);
        this.savedRange = null;
        this.refactoring = false;
      },
      error: (err: any) => {
        this.refactorError = err?.error?.error || 'La correction a échoué. Réessayez.';
        this.savedRange = null;
        this.refactoring = false;
      },
    });
  }

  confirmPublish(): void {
    this.showPublishModal = false;
    this.save(true, this.publishSummary || undefined);
  }

  cancelPublish(): void {
    this.showPublishModal = false;
  }

  private afterSave(saved: Procedure, publish: boolean, changeSummary?: string) {
    if (publish) {
      this.qualityService.publishProcedure(saved.id, changeSummary).subscribe({
        next: () => { this.saving = false; this.router.navigate(['/quality/procedures', saved.id]); },
        error: () => { this.saving = false; this.error = 'Erreur lors de la publication.'; },
      });
    } else {
      this.saving = false;
      this.router.navigate(['/quality/procedures', saved.id]);
    }
  }

  cancel() {
    this.router.navigate(['/quality']);
  }
}
