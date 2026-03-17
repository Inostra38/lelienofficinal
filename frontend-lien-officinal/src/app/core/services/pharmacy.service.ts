import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface PharmacyData {
  id?: number;
  email?: string;
  nom_officine: string;
  siret: string;
  address1: string;
  address2: string;
  postal_code: string;
  city: string;
  region: string;
  country: string;
  vat_number: string;
  pharmacy_type: 'urbaine' | 'rurale' | 'centre-bourg' | 'centre-commercial';
  logo?: string;
  is_premium?: boolean;
  date_joined?: string;
  sms_credits?: number;
  phone?: string;
}

@Injectable({
  providedIn: 'root'
})
export class PharmacyService {
  private http = inject(HttpClient);
  private apiUrl = `${environment.apiUrl}/api/pharmacy`;

  getCurrentPharmacy(): Observable<PharmacyData> {
    return this.http.get<PharmacyData>(`${this.apiUrl}/me/`);
  }

  updatePharmacy(data: Partial<PharmacyData>): Observable<PharmacyData> {
    return this.http.patch<PharmacyData>(`${this.apiUrl}/me/update/`, data);
  }

  uploadLogo(file: File): Observable<any> {
    const formData = new FormData();
    formData.append('logo', file);
    return this.http.patch(`${this.apiUrl}/me/update/`, formData);
  }
}
