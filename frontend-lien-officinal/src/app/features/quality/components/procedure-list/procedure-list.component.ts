import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { QualityService } from '../../services/quality.service';
import { Procedure, ProcedureStatus, ReorderPayload } from '../../models/procedure.model';

interface FlatProc {
  proc: Procedure;
  level: number;
  parentId: number | null;
}

type DropPos = 'before' | 'inside' | 'after';

@Component({
  selector: 'app-procedure-list',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './procedure-list.component.html',
})
export class ProcedureListComponent implements OnInit {
  private qualityService = inject(QualityService);

  tree: Procedure[] = [];
  flatList: FlatProc[] = [];
  loading = true;
  error = '';
  statusFilter: ProcedureStatus | 'all' = 'all';
  expandedIds = new Set<number>();

  draggingId: number | null = null;
  dropTarget: { id: number; pos: DropPos } | null = null;

  readonly statusFilters: { value: ProcedureStatus | 'all'; label: string }[] = [
    { value: 'all', label: 'Tous' },
    { value: 'draft', label: 'Brouillon' },
    { value: 'active', label: 'Actif' },
    { value: 'archived', label: 'Archivé' },
  ];

  readonly categoryLabels: Record<string, string> = {
    dispensation: 'Dispensation', hygiene: 'Hygiène', stock: 'Stock',
    administratif: 'Administratif', autre: 'Autre',
  };

  ngOnInit() { this.load(); }

  load() {
    this.loading = true;
    this.qualityService.getProcedureTree().subscribe({
      next: (data) => { this.tree = data; this.updateFlatList(); this.loading = false; },
      error: () => { this.error = 'Erreur lors du chargement.'; this.loading = false; },
    });
  }

  setFilter(f: ProcedureStatus | 'all') { this.statusFilter = f; this.updateFlatList(); }

  get filteredTree(): Procedure[] {
    return this.statusFilter === 'all' ? this.tree : this.tree.filter(p => p.status === this.statusFilter);
  }

  updateFlatList() {
    this.flatList = this.buildFlat(this.filteredTree, 0, null);
  }

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

  // ─── Helpers arbre ───────────────────────────────────────────────

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

  /** Profondeur maximale du sous-arbre d'un item (0 = feuille) */
  subtreeDepth(proc: Procedure): number {
    if (!proc.children?.length) return 0;
    return 1 + Math.max(...proc.children.map(c => this.subtreeDepth(c)));
  }

  /** "inside" autorisé seulement si target.level + 1 + subtree ≤ 2 */
  canDropInside(target: FlatProc): boolean {
    if (target.level >= 2) return false;
    const dragged = this.findProc(this.draggingId!);
    if (!dragged) return false;
    return target.level + 1 + this.subtreeDepth(dragged) <= 2;
  }

  // ─── Drag & Drop ─────────────────────────────────────────────────

  onDragStart(event: DragEvent, id: number) {
    this.draggingId = id;
    event.dataTransfer!.effectAllowed = 'move';
  }

  onDragOver(event: DragEvent, item: FlatProc) {
    event.preventDefault();
    if (!this.draggingId || item.proc.id === this.draggingId) return;
    if (this.isDescendant(item.proc.id, this.draggingId)) return;

    const el = event.currentTarget as HTMLElement;
    const pct = (event.clientY - el.getBoundingClientRect().top) / el.offsetHeight;

    let pos: DropPos;
    if (pct < 0.28) {
      pos = 'before';
    } else if (pct > 0.72) {
      pos = 'after';
    } else {
      pos = this.canDropInside(item) ? 'inside' : (pct < 0.5 ? 'before' : 'after');
    }

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
    if (!this.dropTarget || !this.draggingId || this.dropTarget.id !== target.proc.id) {
      this.resetDrag(); return;
    }

    const pos = this.dropTarget.pos;
    const srcFlat = this.flatList.find(f => f.proc.id === this.draggingId)!;
    const movedProc = this.findProc(this.draggingId)!;
    const payload: ReorderPayload[] = [];

    // 1. Retirer l'item de son ancien parent
    const oldSiblings = this.getSiblings(srcFlat.parentId);
    oldSiblings.splice(oldSiblings.indexOf(movedProc), 1);

    if (pos === 'inside') {
      // 2a. Devenir dernier enfant de target
      if (!target.proc.children) target.proc.children = [];
      target.proc.children.push(movedProc);
      target.proc.children.forEach((p, i) =>
        payload.push({ id: p.id, parent_id: target.proc.id, position: i }));
    } else {
      // 2b. Insérer comme frère de target
      const newParentId = target.parentId;
      const newSiblings = this.getSiblings(newParentId);
      const idx = newSiblings.indexOf(target.proc);
      newSiblings.splice(pos === 'after' ? idx + 1 : idx, 0, movedProc);
      newSiblings.forEach((p, i) =>
        payload.push({ id: p.id, parent_id: newParentId, position: i }));
    }

    // 3. Renumber ancien parent si différent
    if (srcFlat.parentId !== (pos === 'inside' ? target.proc.id : target.parentId)) {
      oldSiblings.forEach((p, i) => {
        if (!payload.find(x => x.id === p.id))
          payload.push({ id: p.id, parent_id: srcFlat.parentId, position: i });
      });
    }

    this.qualityService.reorderProcedures(payload).subscribe({ next: () => this.load() });
    this.resetDrag();
  }

  onDragEnd() { this.resetDrag(); }

  resetDrag() { this.draggingId = null; this.dropTarget = null; }

  dropClass(item: FlatProc): string {
    if (!this.dropTarget || this.dropTarget.id !== item.proc.id) return '';
    switch (this.dropTarget.pos) {
      case 'before': return 'border-t-2 border-t-green-400';
      case 'after':  return 'border-b-2 border-b-green-400';
      case 'inside': return 'ring-2 ring-inset ring-green-400 bg-green-50/60';
    }
  }

  // ─── Labels / styles ─────────────────────────────────────────────

  statusLabel(s: ProcedureStatus): string {
    return ({ draft: 'Brouillon', active: 'Actif', archived: 'Archivé' } as Record<string, string>)[s] || s;
  }

  statusClass(s: ProcedureStatus): string {
    return ({
      draft: 'bg-amber-50 text-amber-700 border border-amber-200',
      active: 'bg-green-50 text-green-700 border border-green-200',
      archived: 'bg-gray-50 text-gray-500 border border-gray-200',
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

  indentClass(level: number): string {
    return ['pl-4', 'pl-10', 'pl-16'][level] ?? 'pl-4';
  }

  rowBg(level: number): string {
    return ['', 'bg-gray-50/50', 'bg-gray-100/40'][level] ?? '';
  }
}
