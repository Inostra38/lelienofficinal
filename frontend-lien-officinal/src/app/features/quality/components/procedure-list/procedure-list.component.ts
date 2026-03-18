import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, Router } from '@angular/router';
import { QualityService } from '../../services/quality.service';
import { Procedure, ProcedureStatus, ReorderPayload } from '../../models/procedure.model';

interface FlatProc {
  proc: Procedure;
  level: number;
  parentId: number | null;
}

@Component({
  selector: 'app-procedure-list',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './procedure-list.component.html',
})
export class ProcedureListComponent implements OnInit {
  private qualityService = inject(QualityService);
  private router = inject(Router);

  tree: Procedure[] = [];
  flatList: FlatProc[] = [];
  loading = true;
  error = '';
  statusFilter: ProcedureStatus | 'all' = 'all';
  expandedIds = new Set<number>();

  draggingId: number | null = null;
  dragOverId: number | null = null;

  readonly statusFilters: { value: ProcedureStatus | 'all'; label: string }[] = [
    { value: 'all', label: 'Tous' },
    { value: 'draft', label: 'Brouillon' },
    { value: 'active', label: 'Actif' },
    { value: 'archived', label: 'Archivé' },
  ];

  readonly categoryLabels: Record<string, string> = {
    dispensation: 'Dispensation',
    hygiene: 'Hygiène',
    stock: 'Stock',
    administratif: 'Administratif',
    autre: 'Autre',
  };

  ngOnInit() { this.load(); }

  load() {
    this.loading = true;
    this.qualityService.getProcedureTree().subscribe({
      next: (data) => {
        this.tree = data;
        this.updateFlatList();
        this.loading = false;
      },
      error: () => { this.error = 'Erreur lors du chargement.'; this.loading = false; },
    });
  }

  setFilter(f: ProcedureStatus | 'all') {
    this.statusFilter = f;
    this.updateFlatList();
  }

  get filteredTree(): Procedure[] {
    if (this.statusFilter === 'all') return this.tree;
    return this.tree.filter(p => p.status === this.statusFilter);
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
    if (this.expandedIds.has(id)) this.expandedIds.delete(id);
    else this.expandedIds.add(id);
    this.updateFlatList();
  }

  isExpanded(id: number): boolean { return this.expandedIds.has(id); }

  // Retourne la référence au tableau de frères dans l'arbre
  getSiblings(parentId: number | null): Procedure[] {
    if (parentId === null) return this.tree;
    const find = (nodes: Procedure[]): Procedure[] | null => {
      for (const n of nodes) {
        if (n.id === parentId) return n.children ?? [];
        if (n.children) { const r = find(n.children); if (r) return r; }
      }
      return null;
    };
    return find(this.tree) ?? [];
  }

  canDrag(item: FlatProc): boolean {
    return item.level > 0 || this.statusFilter === 'all';
  }

  onDragStart(event: DragEvent, id: number) {
    this.draggingId = id;
    event.dataTransfer!.effectAllowed = 'move';
  }

  onDragOver(event: DragEvent, id: number) {
    event.preventDefault();
    event.dataTransfer!.dropEffect = 'move';
    this.dragOverId = id;
  }

  onDragLeave(id: number) {
    if (this.dragOverId === id) this.dragOverId = null;
  }

  onDrop(event: DragEvent, target: FlatProc) {
    event.preventDefault();
    this.dragOverId = null;

    if (!this.draggingId || this.draggingId === target.proc.id) {
      this.draggingId = null;
      return;
    }

    const src = this.flatList.find(f => f.proc.id === this.draggingId);
    if (!src || src.parentId !== target.parentId) {
      this.draggingId = null;
      return;
    }

    const siblings = this.getSiblings(target.parentId);
    const fromIdx = siblings.findIndex(p => p.id === this.draggingId);
    const toIdx = siblings.findIndex(p => p.id === target.proc.id);

    if (fromIdx === -1 || toIdx === -1) { this.draggingId = null; return; }

    // Réordonner en place
    siblings.splice(toIdx, 0, siblings.splice(fromIdx, 1)[0]);

    const payload: ReorderPayload[] = siblings.map((p, i) => ({
      id: p.id,
      parent_id: target.parentId,
      position: i,
    }));

    this.qualityService.reorderProcedures(payload).subscribe();
    this.draggingId = null;
    this.updateFlatList();
  }

  onDragEnd() {
    this.draggingId = null;
    this.dragOverId = null;
  }

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
