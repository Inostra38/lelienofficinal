import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { QualityNcService } from '../../services/quality-nc.service';
import { QualityService } from '../../services/quality.service';
import { Procedure } from '../../models/procedure.model';

@Component({
  selector: 'app-nc-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './nc-form.component.html',
})
export class NcFormComponent implements OnInit {
  private fb = inject(FormBuilder);
  private router = inject(Router);
  private ncService = inject(QualityNcService);
  private qualityService = inject(QualityService);

  saving = false;
  error = '';
  procedures: Procedure[] = [];

  form = this.fb.group({
    title: ['', Validators.required],
    description: ['', Validators.required],
    severity: ['', Validators.required],
    procedure: [null as number | null],
    due_date: [null as string | null],
  });

  ngOnInit() {
    this.qualityService.getProcedures().subscribe({
      next: (p) => { this.procedures = p.filter(x => x.status === 'active'); },
    });
  }

  submit() {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    this.saving = true;
    this.ncService.createNonConformity({
      title: this.form.value.title!,
      description: this.form.value.description!,
      severity: this.form.value.severity as any,
      procedure: this.form.value.procedure as any,
      due_date: this.form.value.due_date || undefined,
    }).subscribe({
      next: (nc) => { this.router.navigate(['/quality/nc', nc.id]); },
      error: () => { this.saving = false; this.error = 'Erreur lors du signalement.'; },
    });
  }

  cancel() { this.router.navigate(['/quality/nc']); }
}
