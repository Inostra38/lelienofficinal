import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

type MemberRole = 'Titulaire' | 'Adjoint' | 'Préparateur' | 'Étudiant' | 'Apprenti';
type MemberCivility = 'M.' | 'Mme' | 'Autre';

interface TeamMember {
  id: string;
  civility: MemberCivility;
  firstName: string;
  lastName: string;
  role: MemberRole;
  pin: string;
  color: string;
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
  teamMembers: TeamMember[] = [];

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

  // Modal state
  showModal = false;
  isEditMode = false;
  currentEditId: string | null = null;

  // Form data
  formData: Omit<TeamMember, 'id'> = {
    civility: 'M.',
    firstName: '',
    lastName: '',
    role: 'Préparateur',
    pin: '',
    color: 'blue'
  };

  // PIN visibility
  showGeneratedPin = false;
  generatedPin = '';

  // Delete confirmation
  showDeleteConfirm = false;
  deleteTargetId: string | null = null;

  ngOnInit() {
    this.loadTeamMembers();
  }

  loadTeamMembers() {
    // Mock data
    this.teamMembers = [
      {
        id: '1',
        civility: 'Mme',
        firstName: 'Sophie',
        lastName: 'Martin',
        role: 'Titulaire',
        pin: '1234', // Hashé en production
        color: 'blue'
      },
      {
        id: '2',
        civility: 'M.',
        firstName: 'Pierre',
        lastName: 'Dubois',
        role: 'Adjoint',
        pin: '5678',
        color: 'green'
      },
      {
        id: '3',
        civility: 'Mme',
        firstName: 'Marie',
        lastName: 'Lefebvre',
        role: 'Préparateur',
        pin: '9012',
        color: 'purple'
      }
    ];
  }

  get memberCount(): number {
    return this.teamMembers.length;
  }

  openAddModal() {
    this.isEditMode = false;
    this.currentEditId = null;
    this.resetForm();
    this.generatePin();
    this.showModal = true;
  }

  openEditModal(member: TeamMember) {
    this.isEditMode = true;
    this.currentEditId = member.id;
    this.formData = {
      civility: member.civility,
      firstName: member.firstName,
      lastName: member.lastName,
      role: member.role,
      pin: member.pin,
      color: member.color
    };
    this.showGeneratedPin = false;
    this.showModal = true;
  }

  closeModal() {
    this.showModal = false;
    this.resetForm();
  }

  resetForm() {
    this.formData = {
      civility: 'M.',
      firstName: '',
      lastName: '',
      role: 'Préparateur',
      pin: '',
      color: 'blue'
    };
    this.showGeneratedPin = false;
    this.generatedPin = '';
  }

  generatePin() {
    const pin = Math.floor(1000 + Math.random() * 9000).toString();
    this.generatedPin = pin;
    this.formData.pin = pin;
    this.showGeneratedPin = true;

    // Cache le PIN après 10 secondes
    setTimeout(() => {
      this.showGeneratedPin = false;
    }, 10000);
  }

  saveMember() {
    if (this.isEditMode && this.currentEditId) {
      // Mode édition
      const index = this.teamMembers.findIndex(m => m.id === this.currentEditId);
      if (index !== -1) {
        this.teamMembers[index] = {
          id: this.currentEditId,
          ...this.formData
        };
      }
    } else {
      // Mode ajout
      const newMember: TeamMember = {
        id: Date.now().toString(),
        ...this.formData
      };
      this.teamMembers.push(newMember);
    }

    // TODO: Sauvegarder via l'API
    console.log('Saving member:', this.formData);
    this.closeModal();
  }

  confirmDelete(id: string) {
    this.deleteTargetId = id;
    this.showDeleteConfirm = true;
  }

  cancelDelete() {
    this.showDeleteConfirm = false;
    this.deleteTargetId = null;
  }

  deleteMember() {
    if (this.deleteTargetId) {
      this.teamMembers = this.teamMembers.filter(m => m.id !== this.deleteTargetId);
      // TODO: Supprimer via l'API
      console.log('Deleted member:', this.deleteTargetId);
    }
    this.cancelDelete();
  }

  getColorClass(color: string): string {
    return `bg-${color}-500`;
  }

  getColorOption(colorValue: string): ColorOption | undefined {
    return this.colors.find(c => c.value === colorValue);
  }
}
