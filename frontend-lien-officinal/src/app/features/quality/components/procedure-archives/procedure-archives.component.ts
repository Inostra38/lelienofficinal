import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { QualityService } from '../../services/quality.service';
import { Procedure } from '../../models/procedure.model';
import { ConfirmService } from '../../../../core/services/confirm.service';

@Component({
  selector: 'app-procedure-archives',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './procedure-archives.component.html',
})
export class ProcedureArchivesComponent implements OnInit {
  private qualityService = inject(QualityService);
  private confirmService = inject(ConfirmService);

  procedures: Procedure[] = [];
  loading = true;
  error = '';

  ngOnInit() {
    this.qualityService.getArchivedProcedures().subscribe({
      next: (list) => { this.procedures = list; this.loading = false; },
      error: () => { this.error = 'Erreur lors du chargement.'; this.loading = false; },
    });
  }

  async unarchive(p: Procedure) {
    if (!await this.confirmService.ask({ title: 'Restaurer la procédure', message: `Remettre "${p.title}" dans le tableau principal ?`, danger: false })) return;
    this.qualityService.unarchiveProcedure(p.id).subscribe({
      next: () => { this.procedures = this.procedures.filter(x => x.id !== p.id); },
    });
  }

  groupName(p: Procedure): string {
    return (p as any).group_name || '—';
  }
}
