import { Component, EventEmitter, Input, OnInit, Output, inject } from '@angular/core';
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

  /** Mode « verrou d'abonnement » : bouton « Continuer vers le paiement »
   *  bloqué tant que les informations obligatoires ne sont pas complètes. */
  @Input() gateMode = false;
  @Output() completed = new EventEmitter<void>();

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

  private buildUpdatePayload() {
    return {
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
  }

  savePharmacyInfo() {
    this.isLoading = true;
    this.pharmacyService.updatePharmacy(this.buildUpdatePayload()).subscribe({
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

  /**
   * Complétude requise pour souscrire. Tout est obligatoire sauf le complément
   * d'adresse et le logo ; côté téléphone, au moins un des deux suffit.
   */
  isGateComplete(): boolean {
    const d = this.pharmacyData;
    const filled = (v: string) => !!v && v.trim().length > 0;
    return filled(d.name) && filled(d.raisonSociale) && filled(d.address1)
      && filled(d.postalCode) && filled(d.city) && filled(d.region)
      && filled(d.country) && filled(d.siret) && filled(d.vatNumber)
      && filled(d.type) && (filled(d.phoneFixe) || filled(d.phoneMobile));
  }

  /** Enregistre puis, en cas de succès, signale au parent de passer au paiement. */
  saveAndContinue() {
    if (!this.isGateComplete()) return;
    this.isLoading = true;
    this.errorMessage = '';
    this.pharmacyService.updatePharmacy(this.buildUpdatePayload()).subscribe({
      next: () => {
        this.initialData = JSON.stringify(this.pharmacyData);
        this.hasUnsavedChanges = false;
        this.isLoading = false;
        this.completed.emit();
      },
      error: () => {
        this.errorMessage = 'Erreur lors de l\'enregistrement des informations.';
        this.isLoading = false;
      },
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
