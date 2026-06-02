import DOMPurify from 'dompurify';

/**
 * Sanitisation du HTML riche produit par l'éditeur Quill (module Qualité).
 *
 * Sécurité (C4) : le contenu des procédures était rendu via
 * `bypassSecurityTrustHtml`, ce qui désactive le sanitizer Angular et ouvre
 * un XSS stocké (ex. `<img src=x onerror=...>`), d'autant que le contenu peut
 * provenir de l'IA qualité. On purifie systématiquement, à l'écriture comme à
 * la lecture, avec une allowlist stricte limitée au formatage Quill légitime.
 *
 * L'allowlist couvre : titres, paragraphes, gras/italique/souligné/barré,
 * listes, liens, blocs de code, citations, alignement et indentation
 * (classes `ql-*` générées par Quill).
 */
const QUILL_ALLOWED_TAGS = [
  'p', 'br', 'span', 'div',
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
  'strong', 'b', 'em', 'i', 'u', 's', 'strike', 'sub', 'sup',
  'ul', 'ol', 'li',
  'a',
  'blockquote', 'pre', 'code',
  'hr',
];

const QUILL_ALLOWED_ATTR = [
  'href', 'target', 'rel',
  'class',   // Quill encode alignement/indentation via `ql-align-*`, `ql-indent-*`
  'style',   // couleur/fond inline produits par Quill
];

/**
 * Purifie une chaîne HTML avec l'allowlist Quill.
 * Retourne une chaîne sûre, sans script, handler d'événement ni URI dangereuse.
 */
export function sanitizeQuillHtml(html: string | null | undefined): string {
  if (!html) {
    return '';
  }
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: QUILL_ALLOWED_TAGS,
    ALLOWED_ATTR: QUILL_ALLOWED_ATTR,
    // Bloque javascript:, data:, etc. sur href ; n'autorise que http(s) et mailto/tel.
    ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto|tel):|[^a-z]|[a-z+.-]+(?:[^a-z+.\-:]|$))/i,
  });
}
