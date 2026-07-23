import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PharmacyService, PharmacyData } from '../../../../core/services/pharmacy.service';

interface PharmacyFormData {
  name: string;
  raisonSociale: string;
  email: string;          // lecture seule (changement via un flux vérifié dédié)
  address1: string;
  address2: string;
  postalCode: string;
  city: string;
  region: string;
  country: string;
  siret: string;
  vatNumber: string;
  phoneFixe: string;
  phoneMobile: string;
  type: 'urbaine' | 'rurale' | 'centre-bourg' | 'centre-commercial';
  logo?: string;
}

/** 13 régions métropolitaines + 5 DROM — même liste que REGION_CHOICES côté backend. */
const FRENCH_REGIONS = [
  'Auvergne-Rhône-Alpes', 'Bourgogne-Franche-Comté', 'Bretagne', 'Centre-Val de Loire',
  'Corse', 'Grand Est', 'Hauts-de-France', 'Île-de-France', 'Normandie',
  'Nouvelle-Aquitaine', 'Occitanie', 'Pays de la Loire', "Provence-Alpes-Côte d'Azur",
  'Guadeloupe', 'Martinique', 'Guyane', 'La Réunion', 'Mayotte',
];

@Component({
  selector: 'app-pharmacy-info',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './pharmacy-info.component.html',
  styleUrl: './pharmacy-info.component.css'
})
export class PharmacyInfoComponent implements OnInit {
  private pharmacyService = inject(PharmacyService);

  pharmacyData: PharmacyFormData = {
    name: '', raisonSociale: '', email: '', address1: '', address2: '',
    postalCode: '', city: '', region: '', country: 'France', siret: '',
    vatNumber: '', phoneFixe: '', phoneMobile: '', type: 'urbaine'
  };

  readonly regions = FRENCH_REGIONS;

  pharmacyTypes = [
    { value: 'urbaine', label: 'Urbaine' },
    { value: 'rurale', label: 'Rurale' },
    { value: 'centre-bourg', label: 'Centre Bourg' },
    { value: 'centre-commercial', label: 'Centre Commercial' }
  ];

  hasUnsavedChanges = false;
  initialData = '';
  isLoading = false;
  errorMessage = '';

  ngOnInit() {
    this.loadPharmacyData();
  }

  loadPharmacyData() {
    this.isLoading = true;
    this.pharmacyService.getCurrentPharmacy().subscribe({
      next: (data: PharmacyData) => {
        this.pharmacyData = {
          name: data.nom_officine, raisonSociale: data.raison_sociale ?? '',
          email: data.email ?? '',
          address1: data.address1, address2: data.address2,
          postalCode: data.postal_code, city: data.city,
          // Région hors des 18 valeurs (ancienne saisie libre) → vide, à re-choisir,
          // sinon le <select> l'ignore et le backend rejette la valeur au save.
          region: FRENCH_REGIONS.includes(data.region) ? data.region : '',
          country: data.country, siret: data.siret, vatNumber: data.vat_number,
          phoneFixe: data.phone_fixe ?? '', phoneMobile: data.phone_mobile ?? '',
          type: data.pharmacy_type, logo: data.logo
        };
        this.initialData = JSON.stringify(this.pharmacyData);
        this.isLoading = false;
      },
      error: () => {
        this.errorMessage = 'Impossible de charger les données de la pharmacie';
        this.isLoading = false;
      }
    });
  }

  onDataChange() {
    this.hasUnsavedChanges = JSON.stringify(this.pharmacyData) !== this.initialData;
  }

  savePharmacyInfo() {
    this.isLoading = true;
    const updateData = {
      nom_officine: this.pharmacyData.name,
      raison_sociale: this.pharmacyData.raisonSociale,
      address1: this.pharmacyData.address1,
      address2: this.pharmacyData.address2,
      postal_code: this.pharmacyData.postalCode,
      city: this.pharmacyData.city,
      region: this.pharmacyData.region,
      country: this.pharmacyData.country,
      siret: this.pharmacyData.siret,
      vat_number: this.pharmacyData.vatNumber,
      phone_fixe: this.pharmacyData.phoneFixe,
      phone_mobile: this.pharmacyData.phoneMobile,
      pharmacy_type: this.pharmacyData.type
    };
    this.pharmacyService.updatePharmacy(updateData).subscribe({
      next: () => {
        this.initialData = JSON.stringify(this.pharmacyData);
        this.hasUnsavedChanges = false;
        this.isLoading = false;
      },
      error: () => {
        this.errorMessage = 'Erreur lors de la sauvegarde';
        this.isLoading = false;
      }
    });
  }

  onLogoUpload(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files[0]) {
      this.pharmacyService.uploadLogo(input.files[0]).subscribe({
        next: () => this.loadPharmacyData(),
        error: () => { this.errorMessage = 'Erreur lors de l\'upload du logo'; }
      });
    }
  }

}
