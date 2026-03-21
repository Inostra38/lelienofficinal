import { environment } from '../../../environments/environment';
import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { tap } from 'rxjs/operators';
import { AuthService } from '../auth/auth.service';

export interface WizardCategory {
  id: number;
  nom: string;
}

export interface WizardResource {
  id: number;
  titre: string;
  description_officielle: string;
  type: string;
}

export interface ClassifiedResource {
  resource_id: number;
  category: string;
}

export interface WizardCollaborator {
  first_name: string;
  last_name: string;
  role: string;
  pin: string;
}

export interface WizardState {
  pharmacy: {
    nom_officine: string;
    city: string;
  };
  selectedCategories: string[];
  selectedResources: WizardResource[];
  classifiedResources: ClassifiedResource[];
  collaborators: WizardCollaborator[];
}

@Injectable({
  providedIn: 'root'
})
export class OnboardingService {
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private baseUrl = environment.apiUrl + '/api';

  // État global du wizard
  state = signal<WizardState>({
    pharmacy: { nom_officine: '', city: '' },
    selectedCategories: [],
    selectedResources: [],
    classifiedResources: [],
    collaborators: [],
  });

  // ── API calls ──────────────────────────────────────────

  getWizardCategories() {
    return this.http.get<WizardCategory[]>(`${this.baseUrl}/wizard/categories/`);
  }

  getWizardResources() {
    return this.http.get<WizardResource[]>(`${this.baseUrl}/wizard/resources/`);
  }

  classifyResources(categories: string[], resources: WizardResource[]) {
    return this.http.post<ClassifiedResource[]>(`${this.baseUrl}/wizard/classify/`, {
      categories,
      resources,
    });
  }

  completeWizard() {
    const s = this.state();
    return this.http.post<{ success: boolean }>(`${this.baseUrl}/wizard/complete/`, {
      pharmacy: s.pharmacy,
      selected_categories: s.selectedCategories,
      classified_resources: s.classifiedResources,
      collaborators: s.collaborators,
    }).pipe(
      tap(() => this.authService.setOnboardingCompleted())
    );
  }

  // ── State mutators ─────────────────────────────────────

  setPharmacy(data: { nom_officine: string; city: string }) {
    this.state.update(s => ({ ...s, pharmacy: data }));
  }

  setSelectedCategories(categories: string[]) {
    this.state.update(s => ({ ...s, selectedCategories: categories }));
  }

  setSelectedResources(resources: WizardResource[]) {
    this.state.update(s => ({ ...s, selectedResources: resources }));
  }

  setClassifiedResources(classified: ClassifiedResource[]) {
    this.state.update(s => ({ ...s, classifiedResources: classified }));
  }

  setCollaborators(collaborators: WizardCollaborator[]) {
    this.state.update(s => ({ ...s, collaborators: collaborators }));
  }
}
