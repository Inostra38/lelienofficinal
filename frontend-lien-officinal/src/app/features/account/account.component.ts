import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { PharmacyInfoComponent } from './components/pharmacy-info/pharmacy-info.component';
import { TeamManagementComponent } from './components/team-management/team-management.component';

@Component({
  selector: 'app-account',
  standalone: true,
  imports: [CommonModule, PharmacyInfoComponent, TeamManagementComponent],
  templateUrl: './account.component.html',
  styleUrl: './account.component.css'
})
export class AccountComponent {
  constructor(private router: Router) {}

  goBack(): void {
    this.router.navigate(['/dashboard']);
  }
}
