import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PlanningService, ConstraintItem } from '../../../../core/services/planning.service';
import { CollaboratorService, Collaborator } from '../../../../core/services/collaborator.service';

@Component({
  selector: 'app-constraint-manager',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './constraint-manager.component.html',
})
export class ConstraintManagerComponent implements OnInit {
  private planningService     = inject(PlanningService);
  private collaboratorService = inject(CollaboratorService);

  constraints: ConstraintItem[] = [];
  collaborators: Collaborator[]  = [];

  expanded = { regulatory: true, pharmacy: true, personal: true };

  newPharmacyConstraint = '';
  newPersonalConstraint = '';
  newPersonalCollab: number | '' = '';

  ngOnInit() {
    this.load();
    this.collaboratorService.getTeam().subscribe(t => { this.collaborators = t; });
  }

  load() {
    this.planningService.getConstraints().subscribe(c => { this.constraints = c; });
  }

  getByLevel(level: string): ConstraintItem[] {
    return this.constraints.filter(c => c.level === level);
  }

  activeCount(level: string): number {
    return this.constraints.filter(c => c.level === level && c.is_active).length;
  }

  toggleSection(section: 'regulatory' | 'pharmacy' | 'personal') {
    this.expanded[section] = !this.expanded[section];
  }

  toggleConstraint(c: ConstraintItem) {
    this.planningService.updateConstraint(c.id, { is_active: !c.is_active }).subscribe(updated => {
      const idx = this.constraints.findIndex(x => x.id === updated.id);
      if (idx !== -1) this.constraints[idx] = updated;
    });
  }

  addConstraint(level: 'pharmacy' | 'personal') {
    const description = level === 'pharmacy' ? this.newPharmacyConstraint.trim() : this.newPersonalConstraint.trim();
    if (!description) return;
    const payload: any = { level, description };
    if (level === 'personal' && this.newPersonalCollab) {
      payload.collaborator_id = Number(this.newPersonalCollab);
    }
    this.planningService.addConstraint(payload).subscribe(created => {
      this.constraints = [...this.constraints, created];
      if (level === 'pharmacy') this.newPharmacyConstraint = '';
      else { this.newPersonalConstraint = ''; this.newPersonalCollab = ''; }
    });
  }

  deleteConstraint(c: ConstraintItem) {
    this.planningService.deleteConstraint(c.id).subscribe(() => {
      this.constraints = this.constraints.filter(x => x.id !== c.id);
    });
  }
}
