export interface CollaboratorColor {
  base:  string;   // fond shift publié / avatar
  light: string;   // fond shift brouillon
  text:  string;   // texte sur fond light
}

// Keyed by legacy name — garde la compatibilité avec les anciens enregistrements DB
export const COLLABORATOR_COLORS: Record<string, CollaboratorColor> = {
  green:   { base: '#22c55e', light: '#dcfce7', text: '#166534' },
  emerald: { base: '#10b981', light: '#d1fae5', text: '#065f46' },
  teal:    { base: '#14b8a6', light: '#ccfbf1', text: '#134e4a' },
  cyan:    { base: '#06b6d4', light: '#cffafe', text: '#164e63' },
  sky:     { base: '#0ea5e9', light: '#e0f2fe', text: '#0c4a6e' },
  blue:    { base: '#3b82f6', light: '#dbeafe', text: '#1e3a8a' },
  indigo:  { base: '#6366f1', light: '#e0e7ff', text: '#312e81' },
  violet:  { base: '#8b5cf6', light: '#ede9fe', text: '#2e1065' },
  purple:  { base: '#a855f7', light: '#f3e8ff', text: '#4c1d95' },
  fuchsia: { base: '#d946ef', light: '#fae8ff', text: '#701a75' },
  pink:    { base: '#ec4899', light: '#fce7f3', text: '#831843' },
  rose:    { base: '#f43f5e', light: '#ffe4e6', text: '#881337' },
  red:     { base: '#ef4444', light: '#fee2e2', text: '#7f1d1d' },
  orange:  { base: '#f97316', light: '#ffedd5', text: '#7c2d12' },
  amber:   { base: '#f59e0b', light: '#fef3c7', text: '#78350f' },
  yellow:  { base: '#eab308', light: '#fef9c3', text: '#713f12' },
  lime:    { base: '#84cc16', light: '#f7fee7', text: '#1a2e05' },
  slate:   { base: '#64748b', light: '#f1f5f9', text: '#0f172a' },
  gray:    { base: '#6b7280', light: '#f3f4f6', text: '#1f2937' },
};

// Reverse map hex → CollaboratorColor (construit une seule fois)
const _HEX_MAP = new Map<string, CollaboratorColor>(
  Object.values(COLLABORATOR_COLORS).map(c => [c.base.toLowerCase(), c])
);

/**
 * Accepte une valeur hex (#RRGGBB venant de la DB) ou un ancien nom ('blue').
 * Retourne toujours un objet CollaboratorColor valide.
 */
export function resolveColor(color: string): CollaboratorColor {
  if (!color) return COLLABORATOR_COLORS['gray'];
  if (color.startsWith('#')) {
    return _HEX_MAP.get(color.toLowerCase()) ?? COLLABORATOR_COLORS['gray'];
  }
  return COLLABORATOR_COLORS[color] ?? COLLABORATOR_COLORS['gray'];
}

/** Alias rétrocompatible */
export function getCollaboratorColor(color: string): CollaboratorColor {
  return resolveColor(color);
}

/** Palette UI pour le sélecteur de couleur (valeurs hex stockées en DB) */
export const COLLABORATOR_COLOR_PALETTE: { hex: string; label: string }[] = [
  { hex: '#3b82f6', label: 'Bleu' },
  { hex: '#6366f1', label: 'Indigo' },
  { hex: '#8b5cf6', label: 'Violette' },
  { hex: '#a855f7', label: 'Violet' },
  { hex: '#d946ef', label: 'Fuchsia' },
  { hex: '#ec4899', label: 'Rose' },
  { hex: '#f43f5e', label: 'Rose pâle' },
  { hex: '#ef4444', label: 'Rouge' },
  { hex: '#f97316', label: 'Orange' },
  { hex: '#f59e0b', label: 'Ambre' },
  { hex: '#eab308', label: 'Jaune' },
  { hex: '#84cc16', label: 'Citron' },
  { hex: '#22c55e', label: 'Vert' },
  { hex: '#10b981', label: 'Émeraude' },
  { hex: '#14b8a6', label: 'Sarcelle' },
  { hex: '#06b6d4', label: 'Cyan' },
  { hex: '#0ea5e9', label: 'Ciel' },
  { hex: '#64748b', label: 'Ardoise' },
  { hex: '#6b7280', label: 'Gris' },
];
