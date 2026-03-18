import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { QualityService } from '../../services/quality.service';
import { Procedure } from '../../models/procedure.model';

@Component({
  selector: 'app-procedure-detail',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './procedure-detail.component.html',
})
export class ProcedureDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private qualityService = inject(QualityService);

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

  categoryLabel(c: string): string {
    return ({
      dispensation: 'Dispensation',
      hygiene: 'Hygiène',
      stock: 'Stock',
      administratif: 'Administratif',
      autre: 'Autre',
    } as Record<string, string>)[c] || c;
  }

  openLightbox(url: string) { this.lightboxImage = url; }
  closeLightbox() { this.lightboxImage = null; }
}
