import { Component, OnInit, HostListener, ElementRef, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { QualityService } from '../../services/quality.service';
import { Procedure } from '../../models/procedure.model';

@Component({
  selector: 'app-procedure-detail',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './procedure-detail.component.html',
  styleUrl: './procedure-detail.component.scss',
})
export class ProcedureDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private qualityService = inject(QualityService);
  private sanitizer = inject(DomSanitizer);
  private el = inject(ElementRef);

  readProgress = 0;

  @HostListener('window:scroll')
  onWindowScroll() {
    const hostHeight = (this.el.nativeElement as HTMLElement).scrollHeight;
    if (hostHeight < 600) { this.readProgress = 0; return; }
    const scrolled = window.scrollY || document.documentElement.scrollTop;
    const total = document.documentElement.scrollHeight - window.innerHeight;
    this.readProgress = total > 0 ? Math.min(100, (scrolled / total) * 100) : 0;
  }

  safeHtml(content: string): SafeHtml {
    return this.sanitizer.bypassSecurityTrustHtml(content);
  }

  procedure: Procedure | null = null;
  loading = true;
  error = '';
  lightboxImage: string | null = null;

  ngOnInit() {
    const id = +(this.route.snapshot.paramMap.get('id') || 0);
    this.qualityService.getProcedure(id).subscribe({
      next: (p) => { this.procedure = p; this.loading = false; },
      error: () => { this.error = 'Procédure introuvable.'; this.loading = false; },
    });
  }

  publish() {
    if (!this.procedure) return;
    const summary = prompt('Résumé des modifications apportées (facultatif) :', '');
    this.qualityService.publishProcedure(this.procedure.id, summary || undefined).subscribe({
      next: (p) => { this.procedure = p; },
    });
  }

  archive() {
    if (!this.procedure || !confirm('Archiver cette procédure ?')) return;
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

  pilotNames(p: Procedure): string {
    return p.pilots?.length ? p.pilots.map(c => c.full_name).join(', ') : 'Non défini';
  }

  openLightbox(url: string) { this.lightboxImage = url; }
  closeLightbox() { this.lightboxImage = null; }

  getInitials(fullName: string): string {
    const parts = fullName.trim().split(/\s+/);
    return ((parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')).toUpperCase();
  }

  getAvatarColor(name: string): string {
    const colors = ['#1B5E20', '#0D47A1', '#4A148C', '#E65100', '#880E4F', '#006064', '#37474F'];
    let hash = 0;
    for (let i = 0; i < name.length; i++) {
      hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    return colors[Math.abs(hash) % colors.length];
  }
}
