import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CdkDragDrop, DragDropModule, moveItemInArray } from '@angular/cdk/drag-drop';
import { RouterLink } from '@angular/router';
import { QualityService } from '../../services/quality.service';
import { ProcedureGroup } from '../../models/procedure.model';
import { BoardSectionComponent } from '../board-section/board-section.component';

@Component({
  selector: 'app-procedure-boards',
  standalone: true,
  imports: [CommonModule, FormsModule, DragDropModule, RouterLink, BoardSectionComponent],
  templateUrl: './procedure-boards.component.html',
  styleUrl: './procedure-boards.component.scss',
})
export class ProcedureBoardsComponent implements OnInit {
  private qualityService = inject(QualityService);

  groups: ProcedureGroup[] = [];
  loading = true;
  error = '';

  searchQuery = '';

  showNewGroupForm = false;
  newGroupName = '';
  newGroupDescription = '';
  newGroupColor = '#2E7D32';
  creating = false;

  ngOnInit() {
    this.qualityService.getGroups().subscribe({
      next: (g) => { this.groups = g; this.loading = false; },
      error: () => { this.error = 'Erreur lors du chargement.'; this.loading = false; },
    });
  }

  openNewGroupForm() {
    this.showNewGroupForm = true;
    this.newGroupName = '';
    this.newGroupDescription = '';
    this.newGroupColor = '#2E7D32';
  }

  cancelNewGroup() {
    this.showNewGroupForm = false;
  }

  createGroup() {
    if (!this.newGroupName.trim() || this.creating) return;
    this.creating = true;
    this.qualityService.createGroup({
      name: this.newGroupName.trim(),
      description: this.newGroupDescription,
      color: this.newGroupColor,
    }).subscribe({
      next: (created) => {
        this.groups.push(created);
        this.showNewGroupForm = false;
        this.creating = false;
      },
      error: () => { this.creating = false; },
    });
  }

  onGroupDeleted(groupId: number) {
    this.groups = this.groups.filter(g => g.id !== groupId);
  }

  onGroupUpdated(updated: ProcedureGroup) {
    const idx = this.groups.findIndex(g => g.id === updated.id);
    if (idx !== -1) this.groups[idx] = updated;
  }

  onGroupDrop(event: CdkDragDrop<ProcedureGroup[]>) {
    moveItemInArray(this.groups, event.previousIndex, event.currentIndex);
    const orderedIds = this.groups.map(g => g.id);
    this.qualityService.reorderGroups(orderedIds).subscribe();
  }
}
