import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../../environments/environment';

@Injectable({ providedIn: 'root' })
export class DashboardApiService {
  private http = inject(HttpClient);

  // Catégories
  loadCategories() {
    return this.http.get<any>(`${environment.apiUrl}/api/categories/?t=${Date.now()}`);
  }

  createCategory(nom: string) {
    return this.http.post(`${environment.apiUrl}/api/categories/`, { nom });
  }

  deleteCategory(id: number) {
    return this.http.delete(`${environment.apiUrl}/api/categories/${id}/`);
  }

  renameCategory(id: number, nom: string) {
    return this.http.patch(`${environment.apiUrl}/api/categories/${id}/`, { nom });
  }

  reorderCategories(order: number[]) {
    return this.http.post(`${environment.apiUrl}/api/categories/reorder/`, { order });
  }

  // Cartes
  loadLibrary() {
    return this.http.get<any[]>(`${environment.apiUrl}/api/catalog/cards/`);
  }

  movePrivateCard(cardId: number, categoryId: number) {
    const fd = new FormData();
    fd.append('category', categoryId.toString());
    return this.http.patch(`${environment.apiUrl}/api/cards/${cardId}/`, fd);
  }

  assignCardCategory(cardId: number, categoryId: number) {
    return this.http.patch(`${environment.apiUrl}/api/cards/${cardId}/assign-category/`, { category: categoryId });
  }

  reorderCards(items: { id: number; type: string; ordre: number }[]) {
    return this.http.post(`${environment.apiUrl}/api/cards/reorder/`, { items });
  }

  deleteCard(id: number) {
    return this.http.delete(`${environment.apiUrl}/api/cards/${id}/`);
  }

  toggleCardVisibility(id: number) {
    return this.http.post(`${environment.apiUrl}/api/cards/${id}/toggle-visibility/`, {});
  }

  toggleCardFavorite(id: number) {
    return this.http.post<any>(`${environment.apiUrl}/api/cards/${id}/toggle-favorite/`, {});
  }

  createCard(formData: FormData) {
    return this.http.post(`${environment.apiUrl}/api/cards/`, formData);
  }
}
