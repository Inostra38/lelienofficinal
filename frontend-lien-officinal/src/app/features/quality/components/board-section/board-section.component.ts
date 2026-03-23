import { Component, Input, Output, EventEmitter, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';
import { QualityService } from '../../services/quality.service';
import { DragDropService } from '../../services/drag-drop.service';
import { AuthService } from '../../../../core/auth/auth.service';
import { ConfirmService } from '../../../../core/services/confirm.service';
import { Procedure, ProcedureGroup, ProcedureStatus, ReorderPayload } from '../../models/procedure.model';

type DropPos = 'before' | 'after';

@Component({
  selector: 'app-board-section',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './board-section.component.html',
})
export class BoardSectionComponent implements OnInit, OnDestroy {
  private qualityService = inject(QualityService);
  private dnd = inject(DragDropService);
  private authService = inject(AuthService);
  private confirmService = inject(ConfirmService);
  private reloadSub?: Subscription;

  @Input() group: ProcedureGroup | null = null;
  @Input() filterQuery = '';
  @Output() groupDeleted = new EventEmitter<number>();
  @Output() groupUpdated = new EventEmitter<ProcedureGroup>();

  isOpen = true;
  isEditing = false;
  editName = '';
  editDescription = '';
  editColor = '';
  loaded = false;
  procedures: Procedure[] = [];
  loading = false;
  error = '';

  draggingId: number | null = null;
  dropTarget: { id: number; pos: DropPos } | null = null;
  emptyDrop = false;

  get groupId(): number | null { return this.group?.id ?? null; }

  canManageQuality(): boolean { return this.authService.canManageQuality(); }

  canEdit(proc: Procedure): boolean {
    if (this.authService.canManageQuality()) return true;
    const collabId = this.authService.getCurrentCollaboratorId();
    if (collabId === null) return false;
    return proc.pilots?.some(p => p.id === collabId) ?? false;
  }

  // ── Tree helpers ────────────────────────────────────────────────────────────

  private matchesQuery(proc: Procedure): boolean {
    if (!this.filterQuery) return true;
    const q = this.filterQuery.toLowerCase();
    return proc.title.toLowerCase().includes(q)
      || (proc.reference?.toLowerCase().includes(q) ?? false);
  }

  get roots(): Procedure[] {
    return this.procedures
      .filter(p => !p.parent_id)
      .filter(p => {
        if (!this.filterQuery) return true;
        return this.matchesQuery(p) || this.childrenOf(p.id).some(c => this.matchesQuery(c));
      })
      .sort((a, b) => a.position - b.position);
  }

  childrenOf(parentId: number): Procedure[] {
    return this.procedures
      .filter(p => p.parent_id === parentId)
      .filter(p => this.matchesQuery(p))
      .sort((a, b) => a.position - b.position);
  }

  // ── Indent / Unindent ───────────────────────────────────────────────────────

  indent(proc: Procedure, event: Event) {
    event.stopPropagation();
    const roots = this.roots;
    const idx = roots.findIndex(p => p.id === proc.id);
    if (idx <= 0) return;
    const newParent = roots[idx - 1];
    const payload: ReorderPayload[] = [{
      id: proc.id,
      position: this.childrenOf(newParent.id).length,
      parent_id: newParent.id,
    }];
    this.qualityService.reorderProcedures(payload).subscribe({ next: () => this.load() });
  }

  unindent(proc: Procedure, event: Event) {
    event.stopPropagation();
    const roots = this.roots;
    const parentIdx = roots.findIndex(p => p.id === proc.parent_id);
    const newRoots = [...roots];
    newRoots.splice(parentIdx + 1, 0, proc);
    const payload: ReorderPayload[] = newRoots.map((p, i) => ({
      id: p.id,
      position: i,
      ...(p.id === proc.id ? { parent_id: null } : {}),
    }));
    this.qualityService.reorderProcedures(payload).subscribe({ next: () => this.load() });
  }

  moveChild(proc: Procedure, dir: 'up' | 'down', event: Event) {
    event.stopPropagation();
    const siblings = this.childrenOf(proc.parent_id!);
    const idx = siblings.findIndex(p => p.id === proc.id);
    if (dir === 'up' && idx <= 0) return;
    if (dir === 'down' && idx >= siblings.length - 1) return;
    const newSiblings = [...siblings];
    const swapIdx = dir === 'up' ? idx - 1 : idx + 1;
    [newSiblings[idx], newSiblings[swapIdx]] = [newSiblings[swapIdx], newSiblings[idx]];
    const payload: ReorderPayload[] = newSiblings.map((p, i) => ({ id: p.id, position: i }));
    this.qualityService.reorderProcedures(payload).subscribe({ next: () => this.load() });
  }

  // ── Group edit ──────────────────────────────────────────────────────────────

  startEdit(event: Event) {
    event.stopPropagation();
    if (!this.group) return;
    this.editName = this.group.name;
    this.editDescription = this.group.description ?? '';
    this.editColor = this.group.color ?? '#2E7D32';
    this.isEditing = true;
  }

  saveEdit(event: Event) {
    event.stopPropagation();
    if (!this.group || !this.editName.trim()) return;
    this.qualityService.updateGroup(this.group.id, {
      name: this.editName.trim(),
      description: this.editDescription,
      color: this.editColor,
    }).subscribe({
      next: (updated) => { this.groupUpdated.emit(updated); this.isEditing = false; },
    });
  }

  cancelEdit(event: Event) {
    event.stopPropagation();
    this.isEditing = false;
  }

  async confirmDelete(event: Event) {
    event.stopPropagation();
    if (!this.group) return;
    if (!await this.confirmService.ask({ title: 'Supprimer le tableau', message: `Supprimer le tableau "${this.group.name}" ? Les procédures qu'il contient seront déplacées dans la bibliothèque générale.`, danger: true })) return;
    this.qualityService.deleteGroup(this.group.id).subscribe({
      next: () => this.groupDeleted.emit(this.group!.id),
    });
  }

  get sectionTitle(): string { return this.group?.name ?? 'Bibliothèque générale'; }

  get procedureCountLabel(): string {
    const count = this.loaded ? this.procedures.length : (this.group?.procedure_count ?? 0);
    const s = count !== 1 ? 's' : '';
    return this.group ? `${count} procédure${s}` : `${count} procédure${s} sans tableau`;
  }

  get newProcedureQueryParams(): Record<string, any> {
    return this.groupId != null ? { group: this.groupId } : {};
  }

  ngOnInit() {
    this.load();
    this.reloadSub = this.dnd.reload$.subscribe(groupId => {
      if (groupId === this.groupId) this.load();
    });
  }

  ngOnDestroy() { this.reloadSub?.unsubscribe(); }

  toggle() { this.isOpen = !this.isOpen; }

  load() {
    this.loading = true;
    this.qualityService.getProceduresForGroup(this.groupId ?? undefined).subscribe({
      next: (data) => { this.procedures = data; this.loading = false; this.loaded = true; },
      error: () => { this.error = 'Erreur lors du chargement.'; this.loading = false; },
    });
  }

  // ── DnD (racines uniquement) ────────────────────────────────────────────────

  onDragStart(event: DragEvent, id: number) {
    this.draggingId = id;
    this.dnd.currentDragId = id;
    this.dnd.sourceGroupId = this.groupId;
    event.dataTransfer!.effectAllowed = 'move';
    event.dataTransfer!.setData('text/plain', String(id));
  }

  onDragOver(event: DragEvent, proc: Procedure) {
    event.preventDefault();
    const activeDragId = this.draggingId ?? this.dnd.currentDragId;
    if (!activeDragId || activeDragId === proc.id) return;
    const el = event.currentTarget as HTMLElement;
    const pct = (event.clientY - el.getBoundingClientRect().top) / el.offsetHeight;
    this.dropTarget = { id: proc.id, pos: pct < 0.5 ? 'before' : 'after' };
    event.dataTransfer!.dropEffect = 'move';
  }

  onDragLeave(event: DragEvent, id: number) {
    const related = event.relatedTarget as Node | null;
    const el = event.currentTarget as HTMLElement;
    if (!related || !el.contains(related)) {
      if (this.dropTarget?.id === id) this.dropTarget = null;
    }
  }

  onDrop(event: DragEvent, target: Procedure) {
    event.preventDefault();
    if (!this.dropTarget || this.dropTarget.id !== target.id) {
      this.resetDrag(); return;
    }

    const activeDragId = this.draggingId ?? this.dnd.currentDragId;
    if (!activeDragId) { this.resetDrag(); return; }

    const pos = this.dropTarget.pos;
    const isCross = this.dnd.sourceGroupId !== this.groupId;

    // DnD ne concerne que les racines
    const siblings = this.roots.filter(p => p.id !== activeDragId);
    const targetIdx = siblings.findIndex(p => p.id === target.id);
    const insertIdx = pos === 'after' ? targetIdx + 1 : targetIdx;
    siblings.splice(insertIdx, 0, { id: activeDragId } as Procedure);

    const payload: ReorderPayload[] = siblings.map((p, i) => ({
      id: p.id, position: i, group_id: this.groupId,
      ...(isCross && p.id === activeDragId ? { parent_id: null } : {}),
    }));

    const sourceGroupId = this.dnd.sourceGroupId;
    this.qualityService.reorderProcedures(payload).subscribe({
      next: () => {
        this.load();
        if (isCross) this.dnd.reload$.next(sourceGroupId);
      },
    });
    this.resetDrag();
  }

  onEmptyDragOver(event: DragEvent) {
    if (!this.dnd.currentDragId || this.dnd.sourceGroupId === this.groupId) return;
    event.preventDefault();
    this.emptyDrop = true;
    event.dataTransfer!.dropEffect = 'move';
  }

  onEmptyDragLeave() { this.emptyDrop = false; }

  onEmptyDrop(event: DragEvent) {
    event.preventDefault();
    this.emptyDrop = false;
    const dragId = this.dnd.currentDragId;
    if (!dragId || this.dnd.sourceGroupId === this.groupId) return;
    const payload: ReorderPayload[] = [
      { id: dragId, position: 0, group_id: this.groupId, parent_id: null },
    ];
    const sourceGroupId = this.dnd.sourceGroupId;
    this.qualityService.reorderProcedures(payload).subscribe({
      next: () => { this.load(); this.dnd.reload$.next(sourceGroupId); },
    });
    this.resetDrag();
  }

  onDragEnd() { this.resetDrag(); }

  resetDrag() {
    this.draggingId = null;
    this.dropTarget = null;
    this.emptyDrop = false;
    this.dnd.currentDragId = null;
    this.dnd.sourceGroupId = null;
  }

  dropClass(proc: Procedure): string {
    if (!this.dropTarget || this.dropTarget.id !== proc.id) return '';
    return this.dropTarget.pos === 'before' ? 'border-t-2 border-t-green-400' : 'border-b-2 border-b-green-400';
  }

  // ── Actions ─────────────────────────────────────────────────────────────────

  pendingPublishProc: Procedure | null = null;
  publishSummary = '';

  openPublishModal(p: Procedure, event: Event) {
    event.stopPropagation(); event.preventDefault();
    this.pendingPublishProc = p;
    this.publishSummary = '';
  }

  confirmPublish() {
    if (!this.pendingPublishProc) return;
    const id = this.pendingPublishProc.id;
    this.pendingPublishProc = null;
    this.qualityService.publishProcedure(id, this.publishSummary || undefined).subscribe({ next: () => this.load() });
  }

  cancelPublish() {
    this.pendingPublishProc = null;
  }

  async archive(p: Procedure, event: Event) {
    event.stopPropagation(); event.preventDefault();
    if (!await this.confirmService.ask({ title: 'Archiver la procédure', message: `Archiver "${p.title}" ? Elle n'apparaîtra plus dans le tableau principal.`, danger: true })) return;
    this.qualityService.archiveProcedure(p.id).subscribe({
      next: () => this.load(),
    });
  }

  // ── Helpers ─────────────────────────────────────────────────────────────────

  /** Version affichée : dernière version publiée si connue, sinon version courante. */
  displayVersion(proc: Procedure): number {
    return proc.last_published_version ?? proc.version;
  }

  statusLabel(s: ProcedureStatus): string {
    return ({ draft: 'Révision en cours', active: 'Actif', archived: 'Archivé' } as Record<string, string>)[s] || s;
  }

  statusClass(s: ProcedureStatus): string {
    return ({
      draft: 'bg-amber-50 text-amber-600 border border-amber-200',
      active: 'bg-green-50 text-green-700 border border-green-200',
      archived: 'bg-gray-100 text-gray-500 border border-gray-200',
    } as Record<string, string>)[s] || '';
  }

  trackById(_: number, proc: Procedure) { return proc.id; }
}
