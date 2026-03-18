import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';
import { QualityService } from '../../services/quality.service';

@Component({
  selector: 'app-group-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './group-form.component.html',
})
export class GroupFormComponent implements OnInit {
  private fb = inject(FormBuilder);
  private qualityService = inject(QualityService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);

  groupId: number | null = null;
  loading = false;
  saving = false;
  error = '';

  readonly colorOptions = [
    '#2E7D32', '#1565C0', '#6A1B9A', '#C62828',
    '#E65100', '#F57F17', '#00695C', '#37474F',
  ];

  form = this.fb.group({
    name: ['', [Validators.required, Validators.maxLength(200)]],
    description: [''],
    color: ['#2E7D32'],
  });

  ngOnInit() {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.groupId = +id;
      this.loading = true;
      this.qualityService.getGroup(this.groupId).subscribe({
        next: (g) => {
          this.form.patchValue({ name: g.name, description: g.description ?? '', color: g.color });
          this.loading = false;
        },
        error: () => { this.error = 'Erreur lors du chargement.'; this.loading = false; },
      });
    }
  }

  get isEdit() { return this.groupId !== null; }

  setColor(c: string) { this.form.get('color')!.setValue(c); }

  save() {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    this.saving = true;
    const v = this.form.value;
    const data: Partial<import('../../models/procedure.model').ProcedureGroup> = {
      name: v.name ?? undefined,
      description: v.description ?? undefined,
      color: v.color ?? undefined,
    };
    const obs = this.groupId
      ? this.qualityService.updateGroup(this.groupId, data)
      : this.qualityService.createGroup(data);

    obs.subscribe({
      next: (g) => this.router.navigate(['/quality/groups', g.id]),
      error: (err) => {
        const msg = err?.error?.name?.[0] || err?.error?.detail || 'Erreur lors de la sauvegarde.';
        this.error = msg;
        this.saving = false;
      },
    });
  }

  cancel() {
    if (this.groupId) {
      this.router.navigate(['/quality/groups', this.groupId]);
    } else {
      this.router.navigate(['/quality/groups']);
    }
  }
}
