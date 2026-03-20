import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { QualityService } from '../../services/quality.service';
import { Procedure } from '../../models/procedure.model';

@Component({
  selector: 'app-procedure-archives',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './procedure-archives.component.html',
})
export class ProcedureArchivesComponent implements OnInit {
  private qualityService = inject(QualityService);

  procedures: Procedure[] = [];
  loading = true;
  error = '';

  ngOnInit() {
    this.qualityService.getArchivedProcedures().subscribe({
      next: (list) => { this.procedures = list; this.loading = false; },
      error: () => { this.error = 'Erreur lors du chargement.'; this.loading = false; },
    });
  }

  unarchive(p: Procedure) {
    if (!confirm(`Remettre "${p.title}" dans le tableau principal ?`)) return;
    this.qualityService.unarchiveProcedure(p.id).subscribe({
      next: () => { this.procedures = this.procedures.filter(x => x.id !== p.id); },
    });
  }

  groupName(p: Procedure): string {
    return (p as any).group_name || '—';
  }
}
