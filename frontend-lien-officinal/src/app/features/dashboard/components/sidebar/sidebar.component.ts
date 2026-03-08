import { Component, EventEmitter, Input, Output, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { Collaborator } from '../../../../core/services/collaborator.service';
import { AdSpaceComponent } from '../../../../shared/ui/ad-space/ad-space.component';
import { AuthService } from '../../../../core/auth/auth.service';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule, AdSpaceComponent],
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.css'
})
export class SidebarComponent {
  @Input() activeCollaborator: Collaborator | null = null;
  @Input() team: Collaborator[] = [];
  @Input() unreadMessagesCount = 0;
  @Input() unseenTasksCount = 0;

  @Output() logout = new EventEmitter<void>();
  @Output() sessionClick = new EventEmitter<Collaborator>();

  private authService = inject(AuthService);
  constructor(private router: Router) {}

  menuItems = [
    { label: 'Tableau de bord', icon: '🏠', active: true, route: '/dashboard' },
    { label: 'Messagerie', icon: '💬', active: false, route: '/messagerie' },
    { label: 'Tâches', icon: '✅', active: false, route: '/taches' },
    { label: 'Planning', icon: '📅', active: false, route: null },
    { label: 'Commandes', icon: '📦', active: false, route: null },
  ];

  onMenuItemNav(route: string | null): void {
    if (route) this.router.navigate([route]);
  }

  // Menu Pharmacie
  @Input() pharmacyName = '';
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
        this.authService.logout();
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