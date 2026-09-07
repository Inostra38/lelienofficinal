# 05 — Front-end Angular

> **Référentiel — bloc 1, Développement Front End :**
> **`C1.b`** responsive et compatibilité navigateurs (§5.6) · **`C1.d`** intégration
> réutilisable et synthétique (Tailwind, §5.6) · **`C2.a`** interactivité et animations
> (§5.6, §5.7) · **`C2.b`** validation des saisies (§5.6) · **`C2.c`** requêtes
> asynchrones et traitement des erreurs (§5.4, §5.7) · **`C2.d`** librairies externes
> (§5.1, §5.6).
> Contribue aussi au **bloc 3** (`C5.a`, `C5.b`) — Angular est l'un des deux frameworks
> présentés. Détail en [annexe](annexe-referentiel-competences.md).

## 5.1 Stack et parti pris

| Élément | Valeur |
|---|---|
| Framework | Angular **20.2** |
| Architecture composants | **100 % standalone** — aucun `NgModule` dans tout le projet |
| Bootstrap | `bootstrapApplication(AppComponent, appConfig)` (`src/main.ts`) |
| Build | `@angular/build:application` (esbuild / Vite), budgets de bundle configurés |
| Langage | TypeScript `~5.9`, mode **strict** complet (`strictTemplates`, `noImplicitOverride`, `noImplicitReturns`…) |
| Style | **Tailwind CSS 3.4** + PostCSS ; quelques `.scss` ponctuels (module qualité) |
| Librairie UI | **aucune** (ni Material ni PrimeNG). `@angular/cdk` uniquement pour le glisser-déposer |
| Éditeur riche | `ngx-quill` + `quill` (procédures qualité, notes) |
| Assainissement HTML | **DOMPurify** |
| Paiement | `@stripe/stripe-js` (Stripe Elements, prélèvement SEPA) |
| Tests | **Karma + Jasmine** (`ng test`) |

Le SSR est **échafaudé** (`@angular/ssr`, `src/server.ts`) mais **désactivé** dans
`angular.json` : la production sert un SPA statique. Voir
[chapitre 12](12-limites-dette-roadmap.md).

## 5.2 Organisation du code (`src/app/`)

```
core/          Logique transverse, singletons — non visuel
  auth/          auth.service, auth.interceptor, 8 guards
  services/      17 services métier (pharmacy, planning, messaging, billing, sms…)
  utils/         date.utils, html-sanitizer, collaborator-colors
shared/        Réutilisable UI
  layouts/       main-layout (coquille authentifiée : sidebar + header)
  ui/            modales maison (move-card, add-link, pin-pad, category-assigner…)
  components/    toast, confirm-modal, subscription-banner, email-banner
  directives/    date-picker.directive (wrap flatpickr, ControlValueAccessor)
features/      Un dossier par domaine fonctionnel
  dashboard/ planning/ tasks/ quality/ messaging/ sms/ account/
  onboarding/ login/ register/ forgot-password/ reset-password/ verify-email/
admin/        Back-office SaaS — bloc ISOLÉ, lazy-loadé, authentification propre
```

La distinction **`core` / `shared` / `features`** matérialise les responsabilités :
services partagés vs briques visuelles réutilisables vs pages métier. Le module
`admin` est le seul vrai périmètre *lazy-loadé* (`loadChildren`), avec son propre
service d'authentification, son intercepteur et ses guards — il ne partage rien avec
l'application pharmacien.

## 5.3 Routing et guards

`src/app/app.routes.ts` définit une route racine `''` portée par `MainLayoutComponent`
et protégée par `authGuard`, avec les pages métier en enfants. Les modules payants
portent en plus `paidAccessGuard` ; certaines actions d'administration fonctionnelle
portent un guard de rôle.

| Guard | Fichier | Rôle |
|---|---|---|
| `authGuard` | `core/auth/auth.guard.ts` | Jeton en mémoire valide ? Sinon tentative de *refresh* silencieux via cookie. Échec → `/login?returnUrl=…`. Onboarding non terminé → `/onboarding`. |
| `noAuthGuard` | `core/auth/no-auth.guard.ts` | Empêche d'accéder à `/login` ou `/register` si déjà connecté. |
| `onboardingGuard` | `core/auth/onboarding.guard.ts` | Garde la route `/onboarding`. |
| `paidAccessGuard` | `core/auth/paid-access.guard.ts` | Modules payants. Consulte `SubscriptionStateService` ; refus → `/account?section=billing` + toast. |
| `qualityManagerGuard` / `planningManagerGuard` / `taskAssignerGuard` | `core/auth/*.guard.ts` | Vérifient une *claim* de permission du jeton (`canManageQuality`, etc.). |
| `adminAuthGuard` / `adminNoAuthGuard` | `admin/admin-auth.guard.ts` | Jeton admin, conservé **en mémoire uniquement**. |

**`authGuard` — reprise de session après rechargement** (`core/auth/auth.guard.ts:7`) :

```ts
export const authGuard: CanActivateFn = (route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  // Token en mémoire et non expiré → accès immédiat
  if (authService.isAuthenticated()) {
    if (!authService.isOnboardingCompleted() && !state.url.startsWith('/onboarding')) {
      router.navigate(['/onboarding']);
      return false;
    }
    return true;
  }

  // Pas de token en mémoire (reload) → tenter un refresh via cookie HttpOnly
  return authService.refreshAccessToken().pipe(
    map(() => { /* … contrôle onboarding … */ return true; }),
    catchError(() => {
      router.navigate(['/login'], { queryParams: { returnUrl: state.url } });
      return of(false);
    })
  );
};
```

Le `returnUrl` est repris par `LoginComponent` après authentification, ce qui permet
de partager un lien profond : l'utilisateur non connecté est renvoyé sur la page
demandée après login.

## 5.4 Couche HTTP — l'intercepteur

`src/app/core/auth/auth.interceptor.ts` est le point de passage unique de toutes les
requêtes. Il assure quatre responsabilités.

### a) Attacher le jeton **uniquement à notre API**

```ts
// C04/C05 : n'attacher le jeton QU'AUX requêtes vers notre API. Sinon une URL
// externe passée à HttpClient (ex. item.final_url d'un lien partenaire) recevait
// le JWT pharmacie → exfiltration.
const isOurApi =
  req.url.startsWith('/') ||
  (!!environment.apiUrl && req.url.startsWith(environment.apiUrl));
const authReq = (token && isOurApi)
  ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
  : req;
```

Le garde `!!environment.apiUrl` évite le piège `startsWith('')` (toujours vrai)
quand `apiUrl` est vide en production.

### b) *Refresh* silencieux sur 401

Sur une réponse `401` (hors endpoints `/token/` et `/api/admin/`), l'intercepteur
appelle `authService.refreshAccessToken()` puis **rejoue la requête d'origine** avec
le nouveau jeton. Si le *refresh* échoue, `logout(router.url)` — l'URL courante
devient le `returnUrl`.

### c) 402 → proposer l'abonnement

```ts
if (err.status === 402) {
  toastService.error(err.error?.detail ?? 'Ce module nécessite un abonnement actif.');
  subscriptionState.invalidate();   // l'état en cache disait « accès ouvert »
  router.navigate(['/account'], { queryParams: { section: 'billing' } });
}
```

On **ne déconnecte pas** : le tableau de bord reste gratuit et accessible.

### d) 403 qualité / 429 → toast explicite

Retours utilisateurs lisibles pour les permissions insuffisantes et le *rate limiting*.

## 5.5 Gestion d'état — sans NgRx

Il n'y a **ni NgRx ni NgXs**. L'état partagé repose sur des **services singletons**
(`providedIn: 'root'`) combinant RxJS et, plus récemment, les **signaux Angular**.

| Service | Mécanisme | Rôle |
|---|---|---|
| `AuthService` (`core/auth/auth.service.ts`) | jetons **en mémoire** (`_accessToken`), `BehaviorSubject` pour la session collaborateur | Source de vérité de l'authentification. Le *refresh token* n'est **jamais** exposé au JS (cookie HttpOnly). Décodage local des *claims* de permission. `refreshAccessToken()` est *single-flight* (une seule requête concurrente). |
| `SubscriptionStateService` (`core/services/subscription-state.service.ts`) | **signaux** (`signal`, `computed`) | `hasPaidAccess`, `trialDaysLeft`. Cache invalidé après souscription ou sur 402. Alimente `paidAccessGuard` et la bannière d'abonnement. |
| `ToastService` | `BehaviorSubject<Toast[]>` | File de notifications éphémères. |
| `MessagingService` | `BehaviorSubject<number>` (non-lus), `Subject<Message>`, `BehaviorSubject<WebSocketStatus>` | Partagé entre la page messagerie et le badge de la barre latérale. |

**Choix assumé :** au vu de la taille de l'application et d'un état majoritairement
« serveur » (rechargé par requête REST), une solution de *store* globale serait
sur-dimensionnée. Les services + RxJS + signaux suffisent et gardent la courbe
d'apprentissage basse.

Les composants « intelligents » (ex. `DashboardComponent`) suivent un patron
constant : chargement REST dans `ngOnInit`, **mises à jour optimistes** (mutation
locale immédiate, appel API, *rollback* + toast d'erreur + rechargement en cas
d'échec).

## 5.6 Interface utilisateur

- **Tailwind CSS** en utilitaire, `src/styles.css` pour le thème global. **Palette
  verte** du projet : `green-700 #15803d` en primaire, `green-600`, `green-50`…
  `emerald` pour les cartes « partenaire », `blue` réservé aux données collaborateurs.
- **Aucune librairie de composants.** Modales, tiroirs, pavé de saisie du PIN,
  sélecteur de catégorie sont dans `shared/ui/`.
- **Responsive** : points de rupture Tailwind + quelques seuils calculés en
  TypeScript via `@HostListener('window:resize')` (ex. bascule vue compacte à
  1280 px dans le tableau de bord).
- **Impression** : `@media print` complet dans `styles.css` (masquage de la barre
  latérale, `@page A4 landscape`) pour imprimer plannings et procédures.
- **Formulaires** : majoritairement *template-driven* (`FormsModule` + `ngModel`) ;
  *reactive forms* là où la validation est complexe (éditeur de procédure, formulaire
  de non-conformité).
- **Éditeur riche** : `quill` encapsulé dans un `ControlValueAccessor`
  (`quill-editor-wrapper`). Toute sortie HTML passe par **DOMPurify**
  (`core/utils/html-sanitizer.ts`, `sanitizeQuillHtml()`) avec liste blanche stricte
  de balises/attributs et blocage des URI `javascript:` / `data:` — le contenu peut
  provenir de l'assistant IA, il est traité comme non fiable (audit `C4`).

## 5.7 Temps réel — WebSocket

Quatre canaux, tous sur l'API `WebSocket` native du navigateur, backend Django
Channels.

| Service | URL | Usage |
|---|---|---|
| `MessagingService` | `…/ws/messaging/conversations/:id/` | messages en direct, accusés de lecture, badge non-lus |
| `TaskWebSocketService` | `…/ws/tasks/` | rafraîchissement du kanban sur événement |
| `SmsWebSocketService` | `…/ws/sms/status/` | passage `PENDING → DELIVERED/FAILED` en direct |
| `QualityAiWsService` | `…/ws/quality/ai/` | requête/réponse IA corrélées par `request_id`, *timeout* 90 s |

**Le jeton JWT est transmis en sous-protocole** (`new WebSocket(url, ['bearer', token])`)
et **jamais en *query string*** — une URL de WebSocket finit dans les logs des proxys
(audit `S18/S19`). Reconnexion automatique avec *backoff* exponentiel, et *refresh*
du jeton avant reconnexion après un rechargement de page.

## 5.8 Build et outillage

- `angular.json` : configuration `production` avec `fileReplacements`
  (`environment.ts` → `environment.prod.ts`), `outputHashing: all`,
  `subresourceIntegrity: true`, budgets `initial` 1,5 Mo (warn) / 2 Mo (error).
- `src/environments/environment.prod.ts` : `apiUrl` et `wsUrl` **vides** → même
  origine (le SPA est servi par Django).
- **Pas d'ESLint configuré** ; Prettier en configuration *inline* dans `package.json`
  (`printWidth: 100`, `singleQuote: true`).
- **Tests** : Karma + Jasmine, 14 fichiers `.spec.ts` (services d'auth, guards,
  composants du tableau de bord, modales). Pas de tests e2e.

> ⚠️ Le job CI « Tests & Build Angular » **ne lance pas** `ng test` : il compile mais
> n'exécute pas la suite Karma. Voir [chapitre 12](12-limites-dette-roadmap.md).
