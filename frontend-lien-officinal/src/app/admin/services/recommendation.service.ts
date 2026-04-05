import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface RecommendationCard {
  id: number;
  titre: string;
  description_officielle: string;
  type: string;
  recommended_at: string;
  recommendation_status: string;
  pharmacy_name: string | null;
  items_count: number;
}

export interface RecommendationItem {
  id: number;
  label: string;
  type: string;
  url: string;
  file: string | null;
  recommended_at: string;
  recommendation_status: string;
  pharmacy_name: string | null;
  parent_card_titre: string | null;
  target_card_titre: string | null;
}

export interface OfficialCard {
  id: number;
  titre: string;
}

export interface RecommendationsResponse {
  cards: RecommendationCard[];
  items: RecommendationItem[];
  counts: {
    pending_cards: number;
    pending_items: number;
  };
}

@Injectable({ providedIn: 'root' })
export class RecommendationService {
  private http = inject(HttpClient);
  private baseUrl = `${environment.apiUrl}/api/admin/recommendations`;

  getRecommendations(status: string = 'PENDING'): Observable<RecommendationsResponse> {
    return this.http.get<RecommendationsResponse>(`${this.baseUrl}/`, {
      params: { status }
    });
  }

  approveCard(cardId: number): Observable<any> {
    return this.http.post(`${this.baseUrl}/card/${cardId}/approve/`, {});
  }

  approveItem(itemId: number, targetCardId?: number): Observable<any> {
    const body = targetCardId ? { target_card_id: targetCardId } : {};
    return this.http.post(`${this.baseUrl}/item/${itemId}/approve/`, body);
  }

  reject(type: 'card' | 'item', id: number): Observable<any> {
    return this.http.post(`${this.baseUrl}/reject/`, { type, id });
  }

  getOfficialCards(): Observable<{ cards: OfficialCard[] }> {
    return this.http.get<{ cards: OfficialCard[] }>(`${this.baseUrl}/official-cards/`);
  }
}
