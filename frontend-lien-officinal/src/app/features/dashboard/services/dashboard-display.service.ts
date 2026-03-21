import { Injectable } from '@angular/core';
import { Category, ResourceCard } from '../dashboard.component';

@Injectable({ providedIn: 'root' })
export class DashboardDisplayService {

  buildDisplay(allCategories: Category[], showOnlyFavorites: boolean): Category[] {
    return JSON.parse(JSON.stringify(allCategories))
      .map((cat: Category) => {
        let cards = [...(cat.cards || []), ...(cat.adopted_cards || [])];
        if (showOnlyFavorites) {
          cards = cards.filter(c => c.is_favorite);
        }
        cards.sort((a, b) => (a.ordre ?? 0) - (b.ordre ?? 0) || a.titre.localeCompare(b.titre));
        return { ...cat, cards };
      });
  }

  search(allCategories: Category[], term: string): Category[] {
    const match = (card: ResourceCard) =>
      [card.titre, card.description_officielle, card.partner?.nom, card.note_courte, card.note_longue]
        .some(v => (v || '').toLowerCase().includes(term)) ||
      (card.items || []).some(i =>
        (i.label || '').toLowerCase().includes(term) || (i.url || '').toLowerCase().includes(term)
      );

    const byCard = allCategories
      .map(cat => ({
        ...cat,
        cards: [...(cat.cards || []), ...(cat.adopted_cards || [])].filter(match)
      }))
      .filter(cat => cat.cards.length > 0);

    // Ajouter catégories dont le nom matche mais pas encore dans la liste
    allCategories
      .filter(cat => (cat.nom || '').toLowerCase().includes(term) && !byCard.find(c => c.id === cat.id))
      .forEach(cat => byCard.push({ ...cat, cards: cat.cards || [] }));

    return byCard;
  }

  getAllFavorites(allCategories: Category[], searchTerm: string): ResourceCard[] {
    const favorites = allCategories.flatMap(cat => [
      ...(cat.cards || []).filter(c => c.is_favorite),
      ...(cat.adopted_cards || []).filter(c => c.is_favorite),
    ]);

    const filtered = searchTerm
      ? favorites.filter(card =>
          [card.titre, card.description_officielle, card.partner?.nom, card.note_courte, card.note_longue]
            .some(v => (v || '').toLowerCase().includes(searchTerm)) ||
          (card.items || []).some(i =>
            (i.label || '').toLowerCase().includes(searchTerm) || (i.url || '').toLowerCase().includes(searchTerm)
          )
        )
      : favorites;

    return filtered.sort((a, b) => a.titre.localeCompare(b.titre));
  }

  updateCardInCategories(allCategories: Category[], updatedCard: any): boolean {
    let found = false;
    allCategories.forEach(cat => {
      const i = (cat.cards || []).findIndex(c => c.id === updatedCard.id);
      if (i !== -1) { cat.cards[i] = { ...cat.cards[i], ...updatedCard }; found = true; }

      if (cat.adopted_cards) {
        const j = cat.adopted_cards.findIndex(c => c.id === updatedCard.id);
        if (j !== -1) { cat.adopted_cards[j] = { ...cat.adopted_cards[j], ...updatedCard }; found = true; }
      }
    });
    return found;
  }
}
