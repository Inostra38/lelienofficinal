import { Component, EventEmitter, Input, Output, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { Router } from '@angular/router';
import { Collaborator } from '../../../../core/services/collaborator.service';
import { AdSpaceComponent } from '../../../../shared/ui/ad-space/ad-space.component';
import { AuthService } from '../../../../core/auth/auth.service';

interface NavItem {
  id: string;
  label: string;
  route: string | null;
  svgPath: string;
}

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive, AdSpaceComponent],
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.css'
})
export class SidebarComponent {
  @Input() activeCollaborator: Collaborator | null = null;
  @Input() team: Collaborator[] = [];
  @Input() unreadMessagesCount = 0;
  @Input() unseenTasksCount = 0;
  @Input() unreadQualityCount = 0;
  @Input() pharmacyName = '';

  @Output() logout = new EventEmitter<void>();
  @Output() sessionClick = new EventEmitter<Collaborator>();

  private authService = inject(AuthService);
  constructor(private router: Router) {}

  isCollapsed = false;
  isPharmacyMenuOpen = false;

  navItems: NavItem[] = [
    {
      id: 'dashboard',
      label: 'Tableau de bord',
      route: '/dashboard',
      svgPath: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6'
    },
    {
      id: 'messagerie',
      label: 'Messagerie',
      route: '/messagerie',
      svgPath: 'M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z'
    },
    {
      id: 'taches',
      label: 'Tâches',
      route: '/taches',
      svgPath: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4'
    },
    {
      id: 'planning',
      label: 'Planning',
      route: '/planning',
      svgPath: 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z'
    },
    {
      id: 'qualite',
      label: 'Qualité',
      route: '/quality',
      svgPath: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z'
    },
    {
      id: 'sms',
      label: 'SMS',
      route: '/sms',
      svgPath: 'M12 18h.01M8 21l4-4 4 4M3 15a4 4 0 004 4h10a4 4 0 004-4V7a4 4 0 00-4-4H7a4 4 0 00-4 4v8z'
    }
  ];

  toggleCollapse(): void {
    this.isCollapsed = !this.isCollapsed;
    if (this.isCollapsed) this.isPharmacyMenuOpen = false;
  }

  togglePharmacyMenu(): void {
    this.isPharmacyMenuOpen = !this.isPharmacyMenuOpen;
  }

  onMenuItemClick(action: string): void {
    this.isPharmacyMenuOpen = false;
    switch (action) {
      case 'account': this.router.navigate(['/account']); break;
      case 'billing': console.log('TODO: Facturation'); break;
      case 'preferences': console.log('TODO: Préférences'); break;
      case 'logout': this.authService.logout(); break;
    }
  }

  getBadgeCount(id: string): number {
    if (id === 'messagerie') return this.unreadMessagesCount;
    if (id === 'taches') return this.unseenTasksCount;
    if (id === 'qualite') return this.unreadQualityCount;
    return 0;
  }

}
