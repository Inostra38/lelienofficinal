/**
 * Utilitaires de calcul de dates — jours fériés et CP.
 * Miroir de la logique Python dans utils.py.
 */

export function getJoursFeries(year: number): Date[] {
  const a = year % 19, b = Math.floor(year / 100), c = year % 100;
  const d = Math.floor(b / 4), e = b % 4, f = Math.floor((b + 8) / 25);
  const g = Math.floor((b - f + 1) / 3), h = (19 * a + b - d - g + 15) % 30;
  const ii = Math.floor(c / 4), k = c % 4, l = (32 + 2 * e + 2 * ii - h - k) % 7;
  const m = Math.floor((a + 11 * h + 22 * l) / 451);
  const eMonth = Math.floor((h + l - 7 * m + 114) / 31);
  const eDay   = ((h + l - 7 * m + 114) % 31) + 1;
  const add = (n: number) => new Date(year, eMonth - 1, eDay + n);
  return [
    new Date(year, 0,  1),  // Jour de l'An
    add(1),                  // Lundi de Pâques
    new Date(year, 4,  1),  // Fête du Travail
    new Date(year, 4,  8),  // Victoire 1945
    add(39),                 // Ascension
    add(50),                 // Lundi de Pentecôte
    new Date(year, 6,  14), // Fête Nationale
    new Date(year, 7,  15), // Assomption
    new Date(year, 10, 1),  // Toussaint
    new Date(year, 10, 11), // Armistice
    new Date(year, 11, 25), // Noël
  ];
}

function isoDate(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

/**
 * Calcule le nombre de jours CP à déduire (CCN art. 13.2.c).
 * Lun–sam hors fériés français. Coupure à 13h.
 *
 * morning  → evening  = journées complètes
 * morning  → morning  = journées − 0,5j fin
 * afternoon → evening  = journées − 0,5j début
 * afternoon → morning  = journées − 1j (0,5+0,5)
 */
export function computeCpDays(
  start: Date,
  end:   Date,
  startPeriod: 'morning' | 'afternoon',
  endPeriod:   'morning' | 'evening',
): number {
  const years = new Set<number>();
  for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
    years.add(d.getFullYear());
  }

  const ferieSet = new Set<string>();
  for (const y of years) {
    for (const f of getJoursFeries(y)) ferieSet.add(isoDate(f));
  }

  const workingDays: string[] = [];
  for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
    if (d.getDay() !== 0 && !ferieSet.has(isoDate(d))) {
      workingDays.push(isoDate(new Date(d)));
    }
  }

  let total = workingDays.length;
  const startIso = isoDate(start);
  const endIso   = isoDate(end);

  if (startPeriod === 'afternoon' && workingDays.includes(startIso)) total -= 0.5;
  if (endPeriod   === 'morning'   && workingDays.includes(endIso))   total -= 0.5;

  return Math.max(0, total);
}
