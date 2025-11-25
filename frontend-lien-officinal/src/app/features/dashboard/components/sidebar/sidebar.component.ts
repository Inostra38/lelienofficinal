import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
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

  menuItems = [
    { label: 'Tableau de bord', icon: '🏠', active: true },
    { label: 'Messagerie', icon: '💬', active: false },
    { label: 'Planning', icon: '📅', active: false },
    { label: 'Commandes', icon: '📦', active: false },
  ];
}