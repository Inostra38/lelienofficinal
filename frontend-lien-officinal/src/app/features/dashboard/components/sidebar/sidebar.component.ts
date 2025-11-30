import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { Collaborator } from '../../../../core/services/collaborator.service';
import { AdSpaceComponent } from '../../../../shared/ui/ad-space/ad-space.component';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule, AdSpaceComponent],
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.css'
})
export class SidebarComponent {
  @Input() activeCollaborator: Collaborator | null = null;
  @Input() team: Collaborator[] = []; // <--- NOUVEAU : On reçoit l'équipe

  @Output() logout = new EventEmitter<void>();
  @Output() sessionClick = new EventEmitter<Collaborator>(); // <--- NOUVEAU : On prévient quand on clique sur qqn

  constructor(private router: Router) {}

  menuItems = [
    { label: 'Tableau de bord', icon: '🏠', active: true },
    { label: 'Messagerie', icon: '💬', active: false },
    { label: 'Planning', icon: '📅', active: false },
    { label: 'Commandes', icon: '📦', active: false },
  ];

  // Menu Pharmacie
  pharmacyName: string = 'Pharmacie des Lilas';
  isPharmacyMenuOpen: boolean = false;

  togglePharmacyMenu(): void {
    this.isPharmacyMenuOpen = !this.isPharmacyMenuOpen;
  }

  onMenuItemClick(action: string): void {
    this.isPharmacyMenuOpen = false;

    switch(action) {
      case 'account':
        this.router.navigate(['/account']);
        break;
      case 'billing':
        console.log('Navigation vers Facturation');
        // TODO: Implémenter la navigation vers la page facturation
        break;
      case 'preferences':
        console.log('Navigation vers Préférences');
        // TODO: Implémenter la navigation vers la page préférences
        break;
      case 'logout':
        console.log('Déconnexion demandée');
        this.logout.emit();
        break;
    }
  }

  getCollaboratorBgClass(color: string): string {
    return `bg-${color}-500`;
  }

  getCollaboratorColorClasses(color: string): string {
    return `bg-${color}-500 border border-${color}-600 hover:border-${color}-700`;
  }
}