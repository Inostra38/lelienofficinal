import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { QualityService } from '../../services/quality.service';
import { ProcedureGroup } from '../../models/procedure.model';
import { ConfirmService } from '../../../../core/services/confirm.service';

@Component({
  selector: 'app-group-list',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './group-list.component.html',
})
export class GroupListComponent implements OnInit {
  private qualityService = inject(QualityService);
  private confirmService = inject(ConfirmService);

  groups: ProcedureGroup[] = [];
  loading = true;
  error = '';

  ngOnInit() { this.load(); }

  load() {
    this.loading = true;
    this.qualityService.getGroups().subscribe({
      next: (data) => { this.groups = data; this.loading = false; },
      error: () => { this.error = 'Erreur lors du chargement.'; this.loading = false; },
    });
  }

  async delete(group: ProcedureGroup, event: Event) {
    event.stopPropagation();
    event.preventDefault();
    if (!await this.confirmService.ask({ title: 'Supprimer le tableau', message: `Supprimer "${group.name}" ? Les procédures seront libérées vers la bibliothèque.`, danger: true })) return;
    this.qualityService.deleteGroup(group.id).subscribe({ next: () => this.load() });
  }

  trackById(_: number, g: ProcedureGroup) { return g.id; }
}
