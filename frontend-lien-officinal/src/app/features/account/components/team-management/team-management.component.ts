import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  CollaboratorService,
  Collaborator,
  CollaboratorCreate,
  MemberRole,
  MemberCivility,
} from '../../../../core/services/collaborator.service';
import { AuthService } from '../../../../core/auth/auth.service';

interface TeamMember {
  id: string;
  civility: MemberCivility;
  firstName: string;
  lastName: string;
  role: MemberRole;
  pin: string;
  color: string;
  email: string;
  can_manage_account: boolean;
  can_manage_team: boolean;
  can_manage_planning: boolean;
  can_manage_quality: boolean;
  is_active: boolean;
  archived_at: string | null;
}

interface MemberFormData {
  civility: MemberCivility;
  firstName: string;
  lastName: string;
  role: MemberRole;
  pin: string;
  color: string;
  email: string;
  can_manage_account: boolean;
  can_manage_team: boolean;
  can_manage_planning: boolean;
  can_manage_quality: boolean;
}

interface ColorOption {
  value: string;
  label: string;
  bgClass: string;
}

@Component({
  selector: 'app-team-management',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './team-management.component.html',
  styleUrl: './team-management.component.css'
})
export class TeamManagementComponent implements OnInit {
  private collaboratorService = inject(CollaboratorService);
  private authService = inject(AuthService);

  teamMembers: TeamMember[] = [];
  isLoading = false;
  errorMessage = '';

  roles: { value: MemberRole; label: string }[] = [
    { value: 'Titulaire', label: 'Titulaire' },
    { value: 'Adjoint', label: 'Adjoint' },
    { value: 'Préparateur', label: 'Préparateur' },
    { value: 'Étudiant', label: 'Étudiant' },
    { value: 'Apprenti', label: 'Apprenti' }
  ];

  civilities: { value: MemberCivility; label: string }[] = [
    { value: 'M.', label: 'M.' },
    { value: 'Mme', label: 'Mme' },
    { value: 'Autre', label: 'Autre' }
  ];

  colors: ColorOption[] = [
    { value: 'blue', label: 'Bleu', bgClass: 'bg-blue-500' },
    { value: 'indigo', label: 'Indigo', bgClass: 'bg-indigo-500' },
    { value: 'purple', label: 'Violet', bgClass: 'bg-purple-500' },
    { value: 'pink', label: 'Rose', bgClass: 'bg-pink-500' },
    { value: 'red', label: 'Rouge', bgClass: 'bg-red-500' },
    { value: 'orange', label: 'Orange', bgClass: 'bg-orange-500' },
    { value: 'amber', label: 'Ambre', bgClass: 'bg-amber-500' },
    { value: 'yellow', label: 'Jaune', bgClass: 'bg-yellow-500' },
    { value: 'lime', label: 'Citron', bgClass: 'bg-lime-500' },
    { value: 'green', label: 'Vert', bgClass: 'bg-green-500' },
    { value: 'emerald', label: 'Émeraude', bgClass: 'bg-emerald-500' },
    { value: 'teal', label: 'Sarcelle', bgClass: 'bg-teal-500' },
    { value: 'cyan', label: 'Cyan', bgClass: 'bg-cyan-500' },
    { value: 'sky', label: 'Ciel', bgClass: 'bg-sky-500' },
    { value: 'violet', label: 'Violette', bgClass: 'bg-violet-500' },
    { value: 'fuchsia', label: 'Fuchsia', bgClass: 'bg-fuchsia-500' },
    { value: 'rose', label: 'Rose pâle', bgClass: 'bg-rose-500' },
    { value: 'slate', label: 'Ardoise', bgClass: 'bg-slate-500' },
    { value: 'gray', label: 'Gris', bgClass: 'bg-gray-500' },
    { value: 'stone', label: 'Pierre', bgClass: 'bg-stone-500' }
  ];

  // Modal ajouter/modifier
  showModal = false;
  isEditMode = false;
  currentEditId: string | null = null;
  formData: MemberFormData = this.emptyForm();
  showGeneratedPin = false;
  generatedPin = '';

  // Archivés
  showArchived = false;

  ngOnInit() {
    this.loadTeamMembers();
  }

  // ── Session collaborateur ──────────────────────────────────────────────────

  get activeCollaboratorId(): number | null {
    return this.authService.getCurrentCollaboratorId();
  }

  get activeCollaborator(): TeamMember | null {
    const id = this.activeCollaboratorId;
    return id ? this.teamMembers.find(m => m.id === String(id)) ?? null : null;
  }

  /** Vrai si la session active a le droit de gérer l'équipe (ou si c'est la pharmacie elle-même). */
  get canManageTeam(): boolean {
    const actor = this.activeCollaborator;
    return actor ? actor.can_manage_team : true;
  }

  // ── Chargement ─────────────────────────────────────────────────────────────

  loadTeamMembers() {
    this.isLoading = true;
    this.collaboratorService.getTeam(this.showArchived).subscribe({
      next: (collaborators: Collaborator[]) => {
        this.teamMembers = collaborators.map(c => ({
          id: c.id?.toString() || '',
          civility: c.civility,
          firstName: c.first_name,
          lastName: c.last_name,
          role: c.role,
          pin: '',
          color: c.color,
          email: c.email || '',
          can_manage_account: c.can_manage_account,
          can_manage_team: c.can_manage_team,
          can_manage_planning: c.can_manage_planning,
          can_manage_quality: c.can_manage_quality,
          is_active: c.is_active !== false,
          archived_at: c.archived_at ?? null,
        }));
        this.isLoading = false;
      },
      error: () => {
        this.errorMessage = 'Impossible de charger l\'équipe';
        this.isLoading = false;
      }
    });
  }

  get activeMembers(): TeamMember[] {
    return this.teamMembers.filter(m => m.is_active);
  }

  get archivedMembers(): TeamMember[] {
    return this.teamMembers.filter(m => !m.is_active);
  }

  get memberCount(): number {
    return this.activeMembers.length;
  }

  toggleShowArchived() {
    this.showArchived = !this.showArchived;
    this.loadTeamMembers();
  }

  // ── Ajouter ────────────────────────────────────────────────────────────────

  openAddModal() {
    if (!this.canManageTeam) return;
    this.isEditMode = false;
    this.currentEditId = null;
    this.formData = this.emptyForm();
    this.generatePin();
    this.showModal = true;
  }

  // ── Modifier ───────────────────────────────────────────────────────────────

  openEditModal(member: TeamMember) {
    if (!this.canManageTeam) return;
    this.isEditMode = true;
    this.currentEditId = member.id;
    this.formData = {
      civility: member.civility,
      firstName: member.firstName,
      lastName: member.lastName,
      role: member.role,
      pin: '',
      color: member.color,
      email: member.email,
      can_manage_account: member.can_manage_account,
      can_manage_team: member.can_manage_team,
      can_manage_planning: member.can_manage_planning,
      can_manage_quality: member.can_manage_quality,
    };
    this.showGeneratedPin = false;
    this.showModal = true;
  }

  closeModal() {
    this.showModal = false;
    this.isEditMode = false;
    this.currentEditId = null;
    this.formData = this.emptyForm();
    this.showGeneratedPin = false;
    this.generatedPin = '';
  }

  private emptyForm(): MemberFormData {
    return {
      civility: 'M.',
      firstName: '',
      lastName: '',
      role: 'Préparateur',
      pin: '',
      color: 'blue',
      email: '',
      can_manage_account: false,
      can_manage_team: false,
      can_manage_planning: false,
      can_manage_quality: false,
    };
  }

  generatePin() {
    const pin = Math.floor(1000 + Math.random() * 9000).toString();
    this.generatedPin = pin;
    this.formData.pin = pin;
    this.showGeneratedPin = true;
    setTimeout(() => { this.showGeneratedPin = false; }, 10000);
  }

  saveMember() {
    this.isLoading = true;
    this.errorMessage = '';

    if (this.isEditMode && this.currentEditId) {
      const updateData: Partial<Collaborator> = {
        civility: this.formData.civility,
        first_name: this.formData.firstName,
        last_name: this.formData.lastName,
        role: this.formData.role,
        color: this.formData.color,
        email: this.formData.email || undefined,
        can_manage_account: this.formData.can_manage_account,
        can_manage_team: this.formData.can_manage_team,
        can_manage_planning: this.formData.can_manage_planning,
        can_manage_quality: this.formData.can_manage_quality,
        ...(this.formData.pin ? { pin: this.formData.pin } : {})
      };
      this.collaboratorService.updateCollaborator(parseInt(this.currentEditId), updateData).subscribe({
        next: () => { this.loadTeamMembers(); this.closeModal(); this.isLoading = false; },
        error: (err) => { this.errorMessage = err.error?.detail || 'Erreur lors de la mise à jour'; this.isLoading = false; }
      });
    } else {
      const createData: CollaboratorCreate = {
        civility: this.formData.civility,
        first_name: this.formData.firstName,
        last_name: this.formData.lastName,
        role: this.formData.role,
        color: this.formData.color,
        pin: this.formData.pin,
        ...(this.formData.email ? { email: this.formData.email } : {}),
        can_manage_account: this.formData.can_manage_account,
        can_manage_team: this.formData.can_manage_team,
        can_manage_planning: this.formData.can_manage_planning,
        can_manage_quality: this.formData.can_manage_quality,
      };
      this.collaboratorService.createCollaborator(createData).subscribe({
        next: () => { this.closeModal(); this.loadTeamMembers(); this.isLoading = false; },
        error: (err) => { this.errorMessage = err.error?.detail || 'Erreur lors de la création'; this.isLoading = false; }
      });
    }
  }

  // ── Suppression ────────────────────────────────────────────────────────────

  confirmDelete(member: TeamMember) {
    if (!this.canManageTeam) return;
    if (!confirm(`Supprimer ${member.firstName} ${member.lastName} de l'équipe ?`)) return;
    this.isLoading = true;
    this.collaboratorService.deleteCollaborator(parseInt(member.id)).subscribe({
      next: () => { this.loadTeamMembers(); this.isLoading = false; },
      error: (err) => { this.errorMessage = err.error?.detail || 'Erreur lors de la suppression'; this.isLoading = false; }
    });
  }

  // ── Réactivation ───────────────────────────────────────────────────────────

  reactivate(member: TeamMember) {
    if (!this.canManageTeam) return;
    this.isLoading = true;
    this.collaboratorService.reactivate(parseInt(member.id)).subscribe({
      next: () => { this.loadTeamMembers(); this.isLoading = false; },
      error: (err) => { this.errorMessage = err.error?.detail || 'Erreur lors de la réactivation'; this.isLoading = false; }
    });
  }

  // ── Utilitaires ────────────────────────────────────────────────────────────

  isTitulaire(member: TeamMember): boolean {
    return member.role === 'Titulaire';
  }

  isCurrentCollaborator(member: TeamMember): boolean {
    return member.id === String(this.activeCollaboratorId);
  }

  hasAnyPermission(member: TeamMember): boolean {
    return member.can_manage_account || member.can_manage_team
      || member.can_manage_planning || member.can_manage_quality;
  }

  getColorClass(color: string): string {
    return `bg-${color}-500`;
  }

  getColorOption(colorValue: string): ColorOption | undefined {
    return this.colors.find(c => c.value === colorValue);
  }

  getRoleBadgeClass(role: MemberRole): string {
    switch (role) {
      case 'Titulaire':   return 'bg-green-100 text-green-800';
      case 'Adjoint':     return 'bg-blue-100 text-blue-800';
      case 'Préparateur': return 'bg-gray-100 text-gray-700';
      case 'Étudiant':    return 'bg-yellow-100 text-yellow-800';
      case 'Apprenti':    return 'bg-orange-100 text-orange-800';
      default:            return 'bg-gray-100 text-gray-700';
    }
  }
}
