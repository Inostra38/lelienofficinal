import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { PharmacyInfoComponent } from './components/pharmacy-info/pharmacy-info.component';
import { AccountSecurityComponent } from './components/account-security/account-security.component';
import { TeamManagementComponent } from './components/team-management/team-management.component';
import { AccountBillingComponent } from './components/account-billing/billing.component';

type Section = 'information' | 'securite' | 'equipe' | 'facturation';

@Component({
  selector: 'app-account',
  standalone: true,
  imports: [CommonModule, PharmacyInfoComponent, AccountSecurityComponent, TeamManagementComponent, AccountBillingComponent],
  templateUrl: './account.component.html',
  styleUrl: './account.component.css'
})
export class AccountComponent {
  activeSection: Section = 'information';

  navItems: { id: Section; label: string; icon: string }[] = [
    {
      id: 'information',
      label: 'Informations',
      icon: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4'
    },
    {
      id: 'securite',
      label: 'Sécurité du compte',
      icon: 'M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z'
    },
    {
      id: 'equipe',
      label: "Gestion de l'équipe",
      icon: 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z'
    },
    {
      id: 'facturation',
      label: 'Facturation',
      icon: 'M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z'
    }
  ];

  constructor(private router: Router) {}

  goBack(): void {
    this.router.navigate(['/dashboard']);
  }
}
