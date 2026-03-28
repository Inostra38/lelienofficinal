import { Component, Input, Output, EventEmitter, inject, OnChanges, SimpleChanges, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PlanningService, Shift, TimeAdjustment, CreateAbsenceDto } from '../../../../core/services/planning.service';
import { ToastService } from '../../../../core/services/toast.service';
import { ConfirmService } from '../../../../core/services/confirm.service';

type DrawerTab = 'define' | 'transform';

interface SubForm {
  type: 'split' | 'early_departure' | 'overtime' | 'cp' | null;
  splitTime: string;
  actualEndTime: string;
  overtimeDuration: string; // HH:MM
  note: string;
  splitPreview: { dur1: string; dur2: string } | null;
  cpStartPeriod: 'morning' | 'afternoon';
  cpEndPeriod:   'morning' | 'evening';
  error: string;
}

interface TransformBadge {
  label: string;
  color: 'green' | 'blue' | 'amber' | 'red' | 'purple' | 'gray';
  note?: string;
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

  // ── État post-transformation ──────────────────────────────────────────────
  transformBadge: TransformBadge | null = null;
  splitShift2: Shift | null = null;

  // ── Sous-formulaire Transformer ───────────────────────────────────────────
  sub: SubForm = { type: null, splitTime: '', actualEndTime: '', overtimeDuration: '', note: '', splitPreview: null, cpStartPeriod: 'morning', cpEndPeriod: 'evening', error: '' };
  transforming = false;

  readonly ABSENCE_TYPES = [
    { value: 'cp',                 label: 'CP posé',               danger: false },
    { value: 'maladie',            label: 'Maladie',               danger: false },
    { value: 'conge_exceptionnel', label: 'Congé exceptionnel',    danger: false },
    { value: 'injustifiee',        label: 'Absence injustifiée',   danger: true  },
  ];

  ngOnChanges(changes: SimpleChanges) {
    const shiftChange = changes['shift'];
    const prevId = (shiftChange?.previousValue as Shift | null)?.id;
    const currId = (shiftChange?.currentValue as Shift | null)?.id;
    const isDifferentShift = currId !== prevId;

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
    if (isDifferentShift) {
      // Ouverture d'un shift différent : badge dérivé de l'état persisté du shift
      this.transformBadge = this._badgeFromShiftState(this.shift);
      this.splitShift2 = null;
    }
    // Si même shift rafraîchi par le parent : badge en cours conservé, form mis à jour
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

  // ── Champ modifié manuellement → efface le badge ──────────────────────────

  onFieldChange() {
    this.dirty = true;
    this.transformBadge = null;
  }

  // ── Durée calculée (affichage) ────────────────────────────────────────────

  get duration(): string {
    if (!this.startTime || !this.endTime) return '';
    const [sh, sm] = this.startTime.split(':').map(Number);
    let [eh, em]   = this.endTime.split(':').map(Number);
    let startMins  = sh * 60 + sm;
    let endMins    = eh * 60 + em;
    if (endMins <= startMins) endMins += 24 * 60;
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

    const collaboratorId = this.shift.collaborator?.id;
    const shiftDate      = this.shift.start_datetime.substring(0, 10);
    const cfg: Record<string, { label: string; color: TransformBadge['color'] }> = {
      maladie:            { label: 'Maladie',             color: 'amber' },
      conge_exceptionnel: { label: 'Congé exceptionnel',  color: 'blue'  },
      injustifiee:        { label: 'Absence injustifiée', color: 'red'   },
    };
    const badge = cfg[type] ?? { label: type, color: 'gray' as const };

    this.planningService.transformShift(this.shift.id, type).subscribe({
      next: () => {
        this.toastService.success(`Shift marqué : ${badge.label}`);
        const createsAbsenceRequest = type === 'maladie' || type === 'conge_exceptionnel';
        if (collaboratorId && createsAbsenceRequest) {
          // Crée une AbsenceRequest journée entière (maladie et congé exceptionnel uniquement)
          this.planningService.createAbsence({
            collaborator_id: collaboratorId,
            start_date:   shiftDate,
            end_date:     shiftDate,
            type:         type as CreateAbsenceDto['type'],
            start_period: 'morning',
            end_period:   'evening',
          }).subscribe({
            next:  () => this._reloadAndShow(badge),
            error: () => this._reloadAndShow(badge), // badge affiché même si l'absence existe déjà
          });
        } else {
          this._reloadAndShow(badge);
        }
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
      next: (result) => {
        this.transforming = false;
        const s2 = result.shift_2;
        this.splitShift2 = s2;
        this._applyShift(result.shift_1);
        this.transformBadge = {
          label: 'Scindé en 2',
          color: 'gray',
          note: `Shift 2 : ${s2.start_datetime.substring(11, 16)}–${s2.end_datetime.substring(11, 16)}`,
        };
        this.activeTab = 'define';
        this._resetSub();
        this.toastService.success('Shift scindé en 2.');
        this.transformed.emit();
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
        const dur = this._minsToHM(adj.duration_minutes);
        this.toastService.success(`Départ anticipé enregistré (−${dur}).`);
        this._reloadAndShow({
          label: 'Départ anticipé',
          color: 'amber',
          note: `TimeAdjustment créé : −${dur}`,
        });
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
        this.toastService.success(`Heures sup enregistrées (+${this.sub.overtimeDuration}).`);
        this._reloadAndShow({
          label: 'Heures supplémentaires',
          color: 'green',
          note: `TimeAdjustment créé : +${this.sub.overtimeDuration}`,
        });
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
        this.toastService.success('RCR ajouté.');
        this._reloadAndShow({
          label: 'RCR posé',
          color: 'purple',
          note: 'AbsenceRequest RCR créée',
        });
      },
      error: (err) => { this.transforming = false; this.toastService.error(err?.error?.detail ?? 'Erreur.'); },
    });
  }

  // CP ──────────────────────────────────────────────────────────────────────

  confirmCpTransform() {
    if (!this.shift?.collaborator) return;
    const shiftDate = this.shift.start_datetime.substring(0, 10);
    const sp = this.sub.cpStartPeriod;
    const ep = this.sub.cpEndPeriod;
    if (sp === 'afternoon' && ep === 'morning') return;
    this.transforming = true;
    this.planningService.createAbsence({
      collaborator_id: this.shift.collaborator.id,
      start_date:   shiftDate,
      end_date:     shiftDate,
      type:         'cp',
      start_period: sp,
      end_period:   ep,
    }).subscribe({
      next: () => {
        const label = sp === 'afternoon' ? 'CP — après-midi'
          : ep === 'morning'             ? 'CP — matin'
          :                                'CP — journée complète';
        const days  = (sp === 'afternoon' || ep === 'morning') ? '0,5 j déduit' : '1 j déduit';
        this.toastService.success(`${label} posé.`);
        // Patcher le shift pour que le badge persiste à la réouverture
        this.planningService.updateShift(this.shift!.id, { is_absent: true, absence_type: 'cp' }).subscribe({
          next: () => this._reloadAndShow({ label, color: 'blue', note: days }),
          error: () => {
            // Le patch a échoué mais l'absence est créée — on affiche quand même le badge
            this.transforming = false;
            this.transformBadge = { label, color: 'blue', note: days };
            this.activeTab = 'define';
            this._resetSub();
            this.transformed.emit();
          },
        });
      },
      error: (err) => { this.transforming = false; this.toastService.error(err?.error?.detail ?? 'Erreur.'); },
    });
  }

  // ── Helpers privés ────────────────────────────────────────────────────────

  /** Dérive le badge depuis l'état persisté du shift (is_absent + absence_type). */
  private _badgeFromShiftState(shift: Shift | null): TransformBadge | null {
    if (!shift?.is_absent || !shift.absence_type) return null;
    const cfg: Record<string, { label: string; color: TransformBadge['color'] }> = {
      cp:                 { label: 'CP posé',             color: 'blue'   },
      maladie:            { label: 'Maladie',              color: 'amber'  },
      conge_exceptionnel: { label: 'Congé exceptionnel',   color: 'blue'   },
      injustifiee:        { label: 'Absence injustifiée',  color: 'red'    },
      rcr:                { label: 'RCR posé',             color: 'purple' },
      sans_solde:         { label: 'Sans solde',           color: 'gray'   },
    };
    const c = cfg[shift.absence_type];
    return c ? { label: c.label, color: c.color } : null;
  }

  /** Met à jour le shift local et les champs du formulaire. */
  private _applyShift(s: Shift) {
    this.shift       = s;
    this.startTime   = s.start_datetime.substring(11, 16);
    this.endTime     = s.end_datetime.substring(11, 16);
    this.isPublished = s.is_published;
    this.note        = s.note ?? '';
    this.dirty       = false;
  }

  /** Recharge le shift depuis l'API, affiche le badge, bascule sur "Définir". */
  private _reloadAndShow(badge: TransformBadge) {
    if (!this.shift) return;
    this.planningService.getShift(this.shift.id).subscribe({
      next: (updated) => {
        this.transforming = false;
        this._applyShift(updated);
        this.transformBadge = badge;
        this.activeTab = 'define';
        this._resetSub();
        this.transformed.emit();
      },
      error: () => {
        this.transforming = false;
        this.transformed.emit();
        this.closed.emit();
      },
    });
  }

  private _resetSub() {
    this.sub = { type: null, splitTime: '', actualEndTime: '', overtimeDuration: '', note: '', splitPreview: null, cpStartPeriod: 'morning', cpEndPeriod: 'evening', error: '' };
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
