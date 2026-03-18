import { Component, Input, Output, EventEmitter, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';
import { QualityService } from '../../services/quality.service';
import { DragDropService } from '../../services/drag-drop.service';
import { Procedure, ProcedureGroup, ProcedureStatus, ReorderPayload } from '../../models/procedure.model';

interface FlatProc {
  proc: Procedure;
  level: number;
  parentId: number | null;
}

type DropPos = 'before' | 'inside' | 'after';

@Component({
  selector: 'app-board-section',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './board-section.component.html',
})
export class BoardSectionComponent implements OnInit, OnDestroy {
  private qualityService = inject(QualityService);
  private dnd = inject(DragDropService);
  private reloadSub?: Subscription;

  @Input() group: ProcedureGroup | null = null;
  @Output() groupDeleted = new EventEmitter<number>();
  @Output() groupUpdated = new EventEmitter<ProcedureGroup>();

  isOpen = true;
  isEditing = false;
  editName = '';
  editDescription = '';
  editColor = '';
  loaded = false;
  tree: Procedure[] = [];
  flatList: FlatProc[] = [];
  loading = false;
  error = '';
  expandedIds = new Set<number>();

  draggingId: number | null = null;
  dropTarget: { id: number; pos: DropPos } | null = null;
  emptyDrop = false;

  readonly categoryLabels: Record<string, string> = {
    dispensation: 'Dispensation', hygiene: 'Hygiène', stock: 'Stock',
    administratif: 'Administratif', autre: 'Autre',
  };

  get groupId(): number | null { return this.group?.id ?? null; }

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
      next: (updated) => {
        this.groupUpdated.emit(updated);
        this.isEditing = false;
      },
    });
  }

  cancelEdit(event: Event) {
    event.stopPropagation();
    this.isEditing = false;
  }

  confirmDelete(event: Event) {
    event.stopPropagation();
    if (!this.group) return;
    if (!confirm(`Supprimer le tableau "${this.group.name}" ? Les procédures qu'il contient seront déplacées dans la bibliothèque générale.`)) return;
    this.qualityService.deleteGroup(this.group.id).subscribe({
      next: () => this.groupDeleted.emit(this.group!.id),
    });
  }

  get sectionTitle(): string { return this.group?.name ?? 'Bibliothèque générale'; }

  get procedureCountLabel(): string {
    const count = this.loaded ? this.tree.length : (this.group?.procedure_count ?? 0);
    const s = count !== 1 ? 's' : '';
    return this.group ? `${count} procédure${s}` : `${count} procédure${s} sans tableau`;
  }

  get newProcedureQueryParams(): Record<string, any> {
    return this.groupId != null ? { group: this.groupId } : {};
  }

  get newFolderQueryParams(): Record<string, any> {
    return this.groupId != null ? { group: this.groupId, folder: 'true' } : { folder: 'true' };
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
    this.qualityService.getProcedureTree(this.groupId ?? undefined).subscribe({
      next: (data) => { this.tree = data; this.updateFlatList(); this.loading = false; this.loaded = true; },
      error: () => { this.error = 'Erreur lors du chargement.'; this.loading = false; },
    });
  }

  updateFlatList() { this.flatList = this.buildFlat(this.tree, 0, null); }

  buildFlat(nodes: Procedure[], level: number, parentId: number | null): FlatProc[] {
    const result: FlatProc[] = [];
    for (const proc of nodes) {
      result.push({ proc, level, parentId });
      if (this.expandedIds.has(proc.id) && proc.children?.length) {
        result.push(...this.buildFlat(proc.children, level + 1, proc.id));
      }
    }
    return result;
  }

  toggleExpand(id: number) {
    this.expandedIds.has(id) ? this.expandedIds.delete(id) : this.expandedIds.add(id);
    this.updateFlatList();
  }

  isExpanded(id: number) { return this.expandedIds.has(id); }

  findProc(id: number, nodes = this.tree): Procedure | null {
    for (const n of nodes) {
      if (n.id === id) return n;
      if (n.children) { const r = this.findProc(id, n.children); if (r) return r; }
    }
    return null;
  }

  getSiblings(parentId: number | null): Procedure[] {
    if (parentId === null) return this.tree;
    const find = (nodes: Procedure[]): Procedure[] | null => {
      for (const n of nodes) {
        if (n.id === parentId) return n.children ?? (n.children = []);
        if (n.children) { const r = find(n.children); if (r) return r; }
      }
      return null;
    };
    return find(this.tree) ?? [];
  }

  isDescendant(candidateId: number, ancestorId: number): boolean {
    const src = this.findProc(ancestorId);
    const check = (nodes: Procedure[]): boolean =>
      nodes.some(n => n.id === candidateId || (n.children ? check(n.children) : false));
    return src?.children ? check(src.children) : false;
  }

  subtreeDepth(proc: Procedure): number {
    if (!proc.children?.length) return 0;
    return 1 + Math.max(...proc.children.map(c => this.subtreeDepth(c)));
  }

  canDropInside(target: FlatProc): boolean {
    if (target.level >= 2) return false;
    const dragged = this.findProc(this.draggingId!);
    if (!dragged) return false;
    return target.level + 1 + this.subtreeDepth(dragged) <= 2;
  }

  onDragStart(event: DragEvent, id: number) {
    this.draggingId = id;
    this.dnd.currentDragId = id;
    this.dnd.sourceGroupId = this.groupId;
    event.dataTransfer!.effectAllowed = 'move';
    event.dataTransfer!.setData('text/plain', String(id));
  }

  onDragOver(event: DragEvent, item: FlatProc) {
    event.preventDefault();
    const activeDragId = this.draggingId ?? this.dnd.currentDragId;
    if (!activeDragId) return;
    const isCross = this.dnd.sourceGroupId !== this.groupId;
    // Cross-section: only allow drop at root level (before/after, not inside)
    if (isCross) {
      const el = event.currentTarget as HTMLElement;
      const pct = (event.clientY - el.getBoundingClientRect().top) / el.offsetHeight;
      this.dropTarget = { id: item.proc.id, pos: pct < 0.5 ? 'before' : 'after' };
      event.dataTransfer!.dropEffect = 'move';
      return;
    }
    if (item.proc.id === activeDragId) return;
    if (this.isDescendant(item.proc.id, activeDragId)) return;
    const el = event.currentTarget as HTMLElement;
    const pct = (event.clientY - el.getBoundingClientRect().top) / el.offsetHeight;
    let pos: DropPos;
    if (pct < 0.28) { pos = 'before'; }
    else if (pct > 0.72) { pos = 'after'; }
    else { pos = this.canDropInside(item) ? 'inside' : (pct < 0.5 ? 'before' : 'after'); }
    this.dropTarget = { id: item.proc.id, pos };
    event.dataTransfer!.dropEffect = 'move';
  }

  onDragLeave(event: DragEvent, id: number) {
    const related = event.relatedTarget as Node | null;
    const el = event.currentTarget as HTMLElement;
    if (!related || !el.contains(related)) {
      if (this.dropTarget?.id === id) this.dropTarget = null;
    }
  }

  onDrop(event: DragEvent, target: FlatProc) {
    event.preventDefault();
    if (!this.dropTarget || this.dropTarget.id !== target.proc.id) {
      this.resetDrag(); return;
    }

    const isCross = this.dnd.sourceGroupId !== this.groupId;
    const activeDragId = this.draggingId ?? this.dnd.currentDragId;
    if (!activeDragId) { this.resetDrag(); return; }

    if (isCross) {
      this.handleCrossDrop(activeDragId, target);
      return;
    }

    const pos = this.dropTarget.pos;
    const srcFlat = this.flatList.find(f => f.proc.id === activeDragId)!;
    const movedProc = this.findProc(activeDragId)!;
    const payload: ReorderPayload[] = [];

    const oldSiblings = this.getSiblings(srcFlat.parentId);
    oldSiblings.splice(oldSiblings.indexOf(movedProc), 1);

    if (pos === 'inside') {
      if (!target.proc.children) target.proc.children = [];
      target.proc.children.push(movedProc);
      target.proc.children.forEach((p, i) =>
        payload.push({ id: p.id, parent_id: target.proc.id, position: i, group_id: this.groupId }));
    } else {
      const newParentId = target.parentId;
      const newSiblings = this.getSiblings(newParentId);
      const idx = newSiblings.indexOf(target.proc);
      newSiblings.splice(pos === 'after' ? idx + 1 : idx, 0, movedProc);
      newSiblings.forEach((p, i) =>
        payload.push({ id: p.id, parent_id: newParentId, position: i, group_id: this.groupId }));
    }

    if (srcFlat.parentId !== (pos === 'inside' ? target.proc.id : target.parentId)) {
      oldSiblings.forEach((p, i) => {
        if (!payload.find(x => x.id === p.id))
          payload.push({ id: p.id, parent_id: srcFlat.parentId, position: i, group_id: this.groupId });
      });
    }

    this.qualityService.reorderProcedures(payload).subscribe({ next: () => this.load() });
    this.resetDrag();
  }

  private handleCrossDrop(dragId: number, target: FlatProc) {
    const pos = this.dropTarget!.pos;
    const siblings = this.getSiblings(null); // always root-level for cross-section
    const idx = siblings.indexOf(target.proc);
    // Payload: move the dragged item to this group, place it before/after target
    // The moved proc is not yet in this.tree, so we just tell the backend its new position
    const insertIdx = pos === 'after' ? idx + 1 : idx;
    const payload: ReorderPayload[] = [];
    // Insert a placeholder to compute positions
    const fakeSiblings = [...siblings];
    fakeSiblings.splice(insertIdx, 0, { id: dragId } as Procedure);
    fakeSiblings.forEach((p, i) =>
      payload.push({ id: p.id, parent_id: null, position: i, group_id: this.groupId }));

    const sourceGroupId = this.dnd.sourceGroupId;
    this.qualityService.reorderProcedures(payload).subscribe({
      next: () => {
        this.load();
        this.dnd.reload$.next(sourceGroupId);
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
      { id: dragId, parent_id: null, position: 0, group_id: this.groupId },
    ];
    const sourceGroupId = this.dnd.sourceGroupId;
    this.qualityService.reorderProcedures(payload).subscribe({
      next: () => {
        this.load();
        this.dnd.reload$.next(sourceGroupId);
      },
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

  dropClass(item: FlatProc): string {
    if (!this.dropTarget || this.dropTarget.id !== item.proc.id) return '';
    switch (this.dropTarget.pos) {
      case 'before': return 'border-t-2 border-t-green-400';
      case 'after':  return 'border-b-2 border-b-green-400';
      case 'inside': return 'ring-2 ring-inset ring-green-400 bg-green-50/60';
    }
  }

  statusLabel(s: ProcedureStatus): string {
    return ({ draft: 'Brouillon', active: 'Actif', archived: 'Archivé' } as Record<string, string>)[s] || s;
  }

  statusClass(s: ProcedureStatus): string {
    return ({
      draft: 'bg-amber-50 text-amber-600 border border-amber-200',
      active: 'bg-green-50 text-green-700 border border-green-200',
      archived: 'bg-gray-100 text-gray-500 border border-gray-200',
    } as Record<string, string>)[s] || '';
  }

  publish(p: Procedure, event: Event) {
    event.stopPropagation(); event.preventDefault();
    this.qualityService.publishProcedure(p.id).subscribe({ next: () => this.load() });
  }

  archive(p: Procedure, event: Event) {
    event.stopPropagation(); event.preventDefault();
    if (!confirm(`Archiver "${p.title}" ?`)) return;
    this.qualityService.archiveProcedure(p.id).subscribe({ next: () => this.load() });
  }

  delete(p: Procedure, event: Event) {
    event.stopPropagation(); event.preventDefault();
    if (!confirm(`Supprimer "${p.title}" ?`)) return;
    this.qualityService.deleteProcedure(p.id).subscribe({ next: () => this.load() });
  }

  trackById(_: number, item: FlatProc) { return item.proc.id; }
  indentClass(level: number): string { return ['', 'pl-6', 'pl-12'][level] ?? ''; }
}
