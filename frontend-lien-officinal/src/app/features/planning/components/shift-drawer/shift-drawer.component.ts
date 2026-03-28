import { Component, Input, Output, EventEmitter, inject, OnChanges, SimpleChanges, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PlanningService, Shift, TimeAdjustment } from '../../../../core/services/planning.service';
import { ToastService } from '../../../../core/services/toast.service';
import { ConfirmService } from '../../../../core/services/confirm.service';

type DrawerTab = 'define' | 'transform';

interface SubForm {
  type: 'split' | 'early_departure' | 'overtime' | null;
  splitTime: string;
  actualEndTime: string;
  overtimeDuration: string; // HH:MM
  note: string;
  splitPreview: { dur1: string; dur2: string } | null;
  error: string;
}

@Component({
  selector: 'app-shift-drawer',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './shift-drawer.component.html',
  styleUrl: './shift-drawer.component.scss',
})
export class ShiftDrawerComponent implements OnChanges {
  @Input() shift: Shift | null = null;
  @Input() date: string | null = null;          // ISO YYYY-MM-DD (création)
  @Input() collaboratorId: number | null = null;

  @Output() saved       = new EventEmitter<Shift>();
  @Output() deleted     = new EventEmitter<number>();
  @Output() closed      = new EventEmitter<void>();
  @Output() transformed = new EventEmitter<void>();

  private planningService = inject(PlanningService);
  private toastService    = inject(ToastService);
  private confirmService  = inject(ConfirmService);

  // ── Onglet actif ──────────────────────────────────────────────────────────
  activeTab: DrawerTab = 'define';

  // ── Formulaire Définir ────────────────────────────────────────────────────
  startTime = '';
  endTime   = '';
  isPublished = false;
  note      = '';
  saving    = false;
  dirty     = false;

  // ── Sous-formulaire Transformer ───────────────────────────────────────────
  sub: SubForm = { type: null, splitTime: '', actualEndTime: '', overtimeDuration: '', note: '', splitPreview: null, error: '' };
  transforming = false;

  readonly ABSENCE_TYPES = [
    { value: 'cp',                 label: 'CP posé',               danger: false },
    { value: 'maladie',            label: 'Maladie',               danger: false },
    { value: 'conge_exceptionnel', label: 'Congé exceptionnel',    danger: false },
    { value: 'injustifiee',        label: 'Absence injustifiée',   danger: true  },
  ];

  ngOnChanges(_: SimpleChanges) {
    if (this.shift) {
      this.startTime   = this.shift.start_datetime.substring(11, 16);
      this.endTime     = this.shift.end_datetime.substring(11, 16);
      this.isPublished = this.shift.is_published;
      this.note        = this.shift.note ?? '';
    } else {
      this.startTime = '08:00';
      this.endTime   = '16:00';
      this.isPublished = false;
      this.note = '';
    }
    this.dirty = false;
    this.activeTab = 'define';
    this._resetSub();
  }

  @HostListener('document:keydown.escape')
  onEscape() { this.close(); }

  // ── Fermeture ─────────────────────────────────────────────────────────────

  async close() {
    if (this.dirty) {
      const ok = await this.confirmService.ask({
        title: 'Modifications non sauvegardées',
        message: 'Fermer sans enregistrer ?',
        danger: false,
      });
      if (!ok) return;
    }
    this.closed.emit();
  }

  // ── Durée calculée (affichage) ────────────────────────────────────────────

  get duration(): string {
    if (!this.startTime || !this.endTime) return '';
    const [sh, sm] = this.startTime.split(':').map(Number);
    let [eh, em]   = this.endTime.split(':').map(Number);
    let startMins  = sh * 60 + sm;
    let endMins    = eh * 60 + em;
    if (endMins <= startMins) endMins += 24 * 60; // cross-midnight
    const diff = endMins - startMins;
    const h = Math.floor(diff / 60);
    const m = diff % 60;
    return m > 0 ? `${h}h${String(m).padStart(2, '0')}` : `${h}h`;
  }

  get isCrossMidnight(): boolean {
    if (!this.startTime || !this.endTime) return false;
    const [sh, sm] = this.startTime.split(':').map(Number);
    const [eh, em] = this.endTime.split(':').map(Number);
    return (eh * 60 + em) <= (sh * 60 + sm);
  }

  get amplitudeError(): string | null {
    if (!this.startTime || !this.endTime) return null;
    const [sh, sm] = this.startTime.split(':').map(Number);
    let [eh, em]   = this.endTime.split(':').map(Number);
    let start = sh * 60 + sm, end = eh * 60 + em;
    if (end <= start) end += 24 * 60;
    const hours = (end - start) / 60;
    if (hours > 12) return `Amplitude max. 12h dépassée (${hours.toFixed(1)}h).`;
    if (hours <= 0) return 'La durée doit être positive.';
    return null;
  }

  // ── Sauvegarde ────────────────────────────────────────────────────────────

  save() {
    if (this.amplitudeError) return;
    this.saving = true;
    const startIso = this._buildDatetime(this.shift?.start_datetime ?? this.date ?? '', this.startTime);
    const endIso   = this._buildDatetime(this.shift?.start_datetime ?? this.date ?? '', this.endTime, this.isCrossMidnight);

    const obs = this.shift
      ? this.planningService.updateShift(this.shift.id, { start_datetime: startIso, end_datetime: endIso, is_published: this.isPublished, note: this.note })
      : this.planningService.createShift({ collaborator_id: this.collaboratorId!, start_datetime: startIso, end_datetime: endIso, is_published: this.isPublished, note: this.note } as any);

    obs.subscribe({
      next: (s) => { this.saving = false; this.dirty = false; this.saved.emit(s); this.closed.emit(); },
      error: (err) => { this.saving = false; this.toastService.error(err?.error?.detail ?? 'Erreur lors de la sauvegarde.'); },
    });
  }

  async deleteShift() {
    if (!this.shift) return;
    const ok = await this.confirmService.ask({ title: 'Supprimer le shift', message: 'Supprimer ce shift définitivement ?', danger: true });
    if (!ok) return;
    this.planningService.deleteShift(this.shift.id).subscribe({
      next: () => { this.deleted.emit(this.shift!.id); this.closed.emit(); },
      error: () => this.toastService.error('Erreur lors de la suppression.'),
    });
  }

  // ── Actions Transformer ───────────────────────────────────────────────────

  applyTransform(type: string) {
    if (!this.shift) return;
    this.transforming = true;
    this.planningService.transformShift(this.shift.id, type).subscribe({
      next: () => {
        this.transforming = false;
        const label = this.ABSENCE_TYPES.find(t => t.value === type)?.label ?? type;
        this.toastService.success(`Shift marqué : ${label}`);
        this.transformed.emit();
        this.closed.emit();
      },
      error: (err) => { this.transforming = false; this.toastService.error(err?.error?.detail ?? 'Erreur.'); },
    });
  }

  openSub(type: SubForm['type']) {
    this._resetSub();
    this.sub.type = type;
  }

  // Split ───────────────────────────────────────────────────────────────────

  onSplitTimeChange() {
    this.sub.splitPreview = null;
    this.sub.error = '';
    if (!this.shift || !this.sub.splitTime) return;
    const [sh, sm] = this.shift.start_datetime.substring(11, 16).split(':').map(Number);
    const [eh, em] = this.shift.end_datetime.substring(11, 16).split(':').map(Number);
    const [ch, cm] = this.sub.splitTime.split(':').map(Number);
    let startMins = sh * 60 + sm, endMins = eh * 60 + em;
    let cutMins   = ch * 60 + cm;
    if (endMins <= startMins) endMins += 24 * 60;
    if (cutMins <= startMins) cutMins += 24 * 60;
    if (cutMins <= startMins || cutMins >= endMins) {
      this.sub.error = 'L\'heure de coupure doit être entre le début et la fin.';
      return;
    }
    this.sub.splitPreview = {
      dur1: this._minsToHM(cutMins - startMins),
      dur2: this._minsToHM(endMins - cutMins),
    };
  }

  confirmSplit() {
    if (!this.shift || !this.sub.splitTime || this.sub.error) return;
    this.transforming = true;
    this.planningService.splitShift(this.shift.id, this.sub.splitTime).subscribe({
      next: () => {
        this.transforming = false;
        this.toastService.success('Shift scindé en 2.');
        this.transformed.emit();
        this.closed.emit();
      },
      error: (err) => { this.transforming = false; this.toastService.error(err?.error?.detail ?? 'Erreur lors du split.'); },
    });
  }

  // Départ anticipé ─────────────────────────────────────────────────────────

  confirmEarlyDeparture() {
    if (!this.shift || !this.sub.actualEndTime) return;
    this.transforming = true;
    this.planningService.earlyDeparture(this.shift.id, { actual_end_time: this.sub.actualEndTime, note: this.sub.note }).subscribe({
      next: (adj: TimeAdjustment) => {
        this.transforming = false;
        this.toastService.success(`Départ anticipé enregistré (−${this._minsToHM(adj.duration_minutes)}).`);
        this.transformed.emit();
        this.closed.emit();
      },
      error: (err) => { this.transforming = false; this.toastService.error(err?.error?.detail ?? 'Erreur.'); },
    });
  }

  // Heures sup ──────────────────────────────────────────────────────────────

  confirmOvertime() {
    if (!this.shift || !this.sub.overtimeDuration) return;
    const [h, m] = this.sub.overtimeDuration.split(':').map(Number);
    const mins = h * 60 + (m || 0);
    if (mins <= 0) { this.sub.error = 'Durée invalide.'; return; }
    this.transforming = true;
    this.planningService.overtimeShift(this.shift.id, { duration_minutes: mins, note: this.sub.note }).subscribe({
      next: () => {
        this.transforming = false;
        this.toastService.success(`Heures sup enregistrées (+${this.sub.overtimeDuration}).`);
        this.transformed.emit();
        this.closed.emit();
      },
      error: (err) => { this.transforming = false; this.toastService.error(err?.error?.detail ?? 'Erreur.'); },
    });
  }

  // RCR ─────────────────────────────────────────────────────────────────────

  async confirmRcr() {
    if (!this.shift) return;
    const ok = await this.confirmService.ask({
      title: 'Ajouter un RCR',
      message: 'Ajouter un RCR de récupération approuvé pour ce collaborateur sur cette journée ?',
      danger: false,
    });
    if (!ok) return;
    this.transforming = true;
    this.planningService.rcrShift(this.shift.id).subscribe({
      next: () => {
        this.transforming = false;
        this.toastService.success('RCR ajouté.');
        this.transformed.emit();
        this.closed.emit();
      },
      error: (err) => { this.transforming = false; this.toastService.error(err?.error?.detail ?? 'Erreur.'); },
    });
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  private _resetSub() {
    this.sub = { type: null, splitTime: '', actualEndTime: '', overtimeDuration: '', note: '', splitPreview: null, error: '' };
  }

  private _buildDatetime(ref: string, time: string, nextDay = false): string {
    const base = ref.substring(0, 10);
    const [y, mo, d] = base.split('-').map(Number);
    let day = new Date(y, mo - 1, d);
    if (nextDay) day = new Date(day.getTime() + 86400000);
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${day.getFullYear()}-${pad(day.getMonth() + 1)}-${pad(day.getDate())}T${time}:00`;
  }

  private _minsToHM(mins: number): string {
    const h = Math.floor(mins / 60), m = mins % 60;
    return m > 0 ? `${h}h${String(m).padStart(2, '0')}` : `${h}h`;
  }
}
