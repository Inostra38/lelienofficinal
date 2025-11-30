import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

interface PharmacyData {
  name: string;
  address1: string;
  address2: string;
  postalCode: string;
  city: string;
  region: string;
  country: string;
  siret: string;
  vatNumber: string;
  type: 'urbaine' | 'rurale' | 'centre-bourg' | 'centre-commercial';
  logo?: string;
}

@Component({
  selector: 'app-pharmacy-info',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './pharmacy-info.component.html',
  styleUrl: './pharmacy-info.component.css'
})
export class PharmacyInfoComponent implements OnInit {
  pharmacyData: PharmacyData = {
    name: '',
    address1: '',
    address2: '',
    postalCode: '',
    city: '',
    region: '',
    country: 'France',
    siret: '',
    vatNumber: '',
    type: 'urbaine'
  };

  pharmacyTypes = [
    { value: 'urbaine', label: 'Urbaine' },
    { value: 'rurale', label: 'Rurale' },
    { value: 'centre-bourg', label: 'Centre Bourg' },
    { value: 'centre-commercial', label: 'Centre Commercial' }
  ];

  hasUnsavedChanges = false;
  initialData: string = '';

  ngOnInit() {
    // TODO: Charger les données depuis l'API
    this.loadPharmacyData();
    this.initialData = JSON.stringify(this.pharmacyData);
  }

  loadPharmacyData() {
    // Mock data pour la démo
    this.pharmacyData = {
      name: 'Pharmacie des Lilas',
      address1: '12 Avenue des Fleurs',
      address2: 'Bâtiment A',
      postalCode: '75020',
      city: 'Paris',
      region: 'Île-de-France',
      country: 'France',
      siret: '12345678901234',
      vatNumber: 'FR12345678901',
      type: 'urbaine'
    };
    this.initialData = JSON.stringify(this.pharmacyData);
  }

  onDataChange() {
    const currentData = JSON.stringify(this.pharmacyData);
    this.hasUnsavedChanges = currentData !== this.initialData;
  }

  savePharmacyInfo() {
    // TODO: Sauvegarder les données via l'API
    console.log('Saving pharmacy data:', this.pharmacyData);
    this.initialData = JSON.stringify(this.pharmacyData);
    this.hasUnsavedChanges = false;
    // Afficher une notification de succès
  }

  onLogoUpload(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files[0]) {
      const file = input.files[0];
      // TODO: Upload du fichier et récupération de l'URL
      console.log('Logo selected:', file.name);
    }
  }
}
