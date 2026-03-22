export interface CollaboratorColor {
  base:  string;   // fond shift publié / avatar
  light: string;   // fond shift brouillon
  text:  string;   // texte sur fond light
}

export const COLLABORATOR_COLORS: Record<string, CollaboratorColor> = {
  green:   { base: '#15803d', light: '#dcfce7', text: '#14532d' },
  emerald: { base: '#047857', light: '#d1fae5', text: '#064e3b' },
  teal:    { base: '#0f766e', light: '#ccfbf1', text: '#134e4a' },
  cyan:    { base: '#0e7490', light: '#cffafe', text: '#164e63' },
  sky:     { base: '#0369a1', light: '#e0f2fe', text: '#0c4a6e' },
  blue:    { base: '#1d4ed8', light: '#dbeafe', text: '#1e3a8a' },
  indigo:  { base: '#4338ca', light: '#e0e7ff', text: '#312e81' },
  violet:  { base: '#6d28d9', light: '#ede9fe', text: '#2e1065' },
  purple:  { base: '#7c3aed', light: '#f3e8ff', text: '#4c1d95' },
  fuchsia: { base: '#a21caf', light: '#fae8ff', text: '#701a75' },
  pink:    { base: '#be185d', light: '#fce7f3', text: '#831843' },
  rose:    { base: '#be123c', light: '#ffe4e6', text: '#881337' },
  red:     { base: '#b91c1c', light: '#fee2e2', text: '#7f1d1d' },
  orange:  { base: '#c2410c', light: '#ffedd5', text: '#7c2d12' },
  amber:   { base: '#b45309', light: '#fef3c7', text: '#78350f' },
  yellow:  { base: '#a16207', light: '#fef9c3', text: '#713f12' },
  lime:    { base: '#4d7c0f', light: '#f7fee7', text: '#1a2e05' },
  slate:   { base: '#334155', light: '#f1f5f9', text: '#0f172a' },
  gray:    { base: '#4b5563', light: '#f3f4f6', text: '#1f2937' },
};

export function getCollaboratorColor(color: string): CollaboratorColor {
  return COLLABORATOR_COLORS[color] ?? COLLABORATOR_COLORS['gray'];
}
