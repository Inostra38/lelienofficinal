import { Component, OnInit, HostListener, ElementRef, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { QualityService } from '../../services/quality.service';
import { AuthService } from '../../../../core/auth/auth.service';
import { ConfirmService } from '../../../../core/services/confirm.service';
import { Procedure, ProcedureVersion } from '../../models/procedure.model';
import { getCollaboratorColor } from '../../../../core/utils/collaborator-colors';

@Component({
  selector: 'app-procedure-detail',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './procedure-detail.component.html',
  styleUrl: './procedure-detail.component.scss',
})
export class ProcedureDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private qualityService = inject(QualityService);
  private authService = inject(AuthService);
  private confirmService = inject(ConfirmService);
  private sanitizer = inject(DomSanitizer);
  private el = inject(ElementRef);

  readProgress = 0;
  private readLogged = false;

  canManageQuality(): boolean { return this.authService.canManageQuality(); }

  canEdit(): boolean {
    if (this.authService.canManageQuality()) return true;
    const collabId = this.authService.getCurrentCollaboratorId();
    if (collabId === null || !this.procedure) return false;
    return this.procedure.pilots?.some(p => p.id === collabId) ?? false;
  }

  @HostListener('window:scroll')
  onWindowScroll() {
    const hostHeight = (this.el.nativeElement as HTMLElement).scrollHeight;
    if (hostHeight < 600) { this.readProgress = 0; return; }
    const scrolled = window.scrollY || document.documentElement.scrollTop;
    const total = document.documentElement.scrollHeight - window.innerHeight;
    this.readProgress = total > 0 ? Math.min(100, (scrolled / total) * 100) : 0;
    if (this.readProgress >= 90 && !this.readLogged && this.procedure) {
      this.readLogged = true;
      this.qualityService.logProcedureRead(this.procedure.id).subscribe();
    }
  }

  safeHtml(content: string): SafeHtml {
    return this.sanitizer.bypassSecurityTrustHtml(content);
  }

  /** Dernière version publiée — non null si la procédure est en brouillon et a déjà été publiée. */
  get publishedVersion() {
    if (!this.procedure || this.procedure.status !== 'draft') return null;
    return this.procedure.history?.[0] ?? null;
  }

  /** Contenu à afficher : version sélectionnée > version publiée (si brouillon) > contenu courant. */
  get displayContent(): string {
    return this.selectedVersion?.content ?? this.publishedVersion?.content ?? this.procedure?.content ?? '';
  }

  viewVersion(v: ProcedureVersion) {
    this.selectedVersion = v;
  }

  resetVersion() {
    this.selectedVersion = null;
  }

  procedure: Procedure | null = null;
  selectedVersion: ProcedureVersion | null = null;
  loading = true;
  error = '';
  lightboxImage: string | null = null;

  showPublishModal = false;
  publishSummary = '';

  ngOnInit() {
    const id = +(this.route.snapshot.paramMap.get('id') || 0);
    this.qualityService.getProcedure(id).subscribe({
      next: (p) => {
        this.procedure = p;
        this.loading = false;
        this.qualityService.markProcedureRead(id).subscribe();
      },
      error: () => { this.error = 'Procédure introuvable.'; this.loading = false; },
    });
  }

  openPublishModal() {
    if (!this.procedure) return;
    this.publishSummary = '';
    this.showPublishModal = true;
  }

  confirmPublish() {
    if (!this.procedure) return;
    this.showPublishModal = false;
    this.qualityService.publishProcedure(this.procedure.id, this.publishSummary || undefined).subscribe({
      next: (p) => { this.procedure = p; },
    });
  }

  cancelPublish() {
    this.showPublishModal = false;
  }

  async archive() {
    if (!this.procedure) return;
    if (!await this.confirmService.ask({ title: 'Archiver la procédure', message: `Archiver cette procédure ? Elle n'apparaîtra plus dans le tableau principal.`, danger: true })) return;
    this.qualityService.archiveProcedure(this.procedure.id).subscribe({
      next: (p) => { this.procedure = p; },
    });
  }

  statusLabel(s: string): string {
    return ({ draft: 'Brouillon', active: 'Actif', archived: 'Archivé' } as Record<string, string>)[s] || s;
  }

  statusClass(s: string): string {
    return ({
      draft: 'bg-amber-50 text-amber-700 border border-amber-200',
      active: 'bg-green-50 text-green-700 border border-green-200',
      archived: 'bg-gray-50 text-gray-500 border border-gray-200',
    } as Record<string, string>)[s] || '';
  }

  isReviewOverdue(): boolean {
    if (!this.procedure?.next_review_date) return false;
    return new Date(this.procedure.next_review_date) < new Date();
  }

  pilotNames(p: Procedure): string {
    return p.pilots?.length ? p.pilots.map(c => c.full_name).join(', ') : 'Non défini';
  }

  printProcedure() { window.print(); }

  openLightbox(url: string) { this.lightboxImage = url; }
  closeLightbox() { this.lightboxImage = null; }

  getInitials(fullName: string): string {
    const parts = fullName.trim().split(/\s+/);
    return ((parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')).toUpperCase();
  }

  getAvatarColor(color: string): string {
    return getCollaboratorColor(color).base;
  }
}
