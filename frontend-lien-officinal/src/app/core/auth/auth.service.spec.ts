import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { Router, provideRouter } from '@angular/router';
import { AuthService } from './auth.service';

// ── JWT helpers ───────────────────────────────────────────────────────────────

function makeJwt(payload: object): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const body = btoa(JSON.stringify(payload));
  return `${header}.${body}.fakesig`;
}

function futureExp(): number {
  return Math.floor(Date.now() / 1000) + 3600;
}

function pastExp(): number {
  return Math.floor(Date.now() / 1000) - 3600;
}

describe('AuthService', () => {
  let service: AuthService;
  let httpMock: HttpTestingController;
  let router: Router;

  const apiBase = 'http://127.0.0.1:8000/api';

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        AuthService,
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
      ],
    });
    service = TestBed.inject(AuthService);
    httpMock = TestBed.inject(HttpTestingController);
    router = TestBed.inject(Router);
  });

  afterEach(() => {
    httpMock.verify();
    localStorage.clear();
  });

  // ── active_collaborator_id ─────────────────────────────────────────────────

  it('getCurrentCollaboratorId — retourne null sans token', () => {
    expect(service.getCurrentCollaboratorId()).toBeNull();
  });

  it('getCurrentCollaboratorId — lit collaborator_id depuis JWT collaborateur', () => {
    const jwt = makeJwt({ auth_type: 'collaborator', collaborator_id: 42, exp: futureExp() });
    localStorage.setItem('access_token', jwt);
    const freshService = TestBed.inject(AuthService);
    expect(freshService.getCurrentCollaboratorId() as number | null).toEqual(42);
  });

  it('collaboratorLogin — met à jour collaboratorSubject', () => {
    const pharmJwt = makeJwt({ auth_type: 'pharmacy_account', exp: futureExp() });
    localStorage.setItem('access_token', pharmJwt);
    localStorage.setItem('refresh_token', 'old-refresh');

    const collabJwt = makeJwt({ auth_type: 'collaborator', collaborator_id: 7, exp: futureExp() });

    let emittedIds: (number | null)[] = [];
    service.collaborator$.subscribe(id => emittedIds.push(id));

    service.collaboratorLogin(7, '1234').subscribe();

    const req = httpMock.expectOne(`${apiBase}/team/login/`);
    req.flush({ access: collabJwt, refresh: 'new-refresh' });

    expect(emittedIds[emittedIds.length - 1] as number | null).toEqual(7);
    expect(localStorage.getItem('access_token')).toBe(collabJwt);
  });

  // ── Token expiré ──────────────────────────────────────────────────────────

  it('isAuthenticated — false si token expiré', () => {
    const expired = makeJwt({ exp: pastExp() });
    localStorage.setItem('access_token', expired);
    expect(service.isAuthenticated()).toBeFalse();
  });

  it('isAuthenticated — true si token valide', () => {
    const valid = makeJwt({ exp: futureExp() });
    localStorage.setItem('access_token', valid);
    expect(service.isAuthenticated()).toBeTrue();
  });

  // ── refreshAccessToken ────────────────────────────────────────────────────

  it('refreshAccessToken — refresh invalide → erreur propagée', () => {
    localStorage.setItem('refresh_token', 'bad-refresh');

    let errorReceived = false;
    service.refreshAccessToken().subscribe({ error: () => (errorReceived = true) });

    const req = httpMock.expectOne(`${apiBase}/token/refresh/`);
    req.flush({ detail: 'Token is invalid' }, { status: 401, statusText: 'Unauthorized' });

    expect(errorReceived).toBeTrue();
  });

  it('refreshAccessToken — succès → nouveau token stocké', () => {
    localStorage.setItem('refresh_token', 'valid-refresh');
    const newAccess = makeJwt({ exp: futureExp() });

    let received = '';
    service.refreshAccessToken().subscribe(t => (received = t));

    const req = httpMock.expectOne(`${apiBase}/token/refresh/`);
    req.flush({ access: newAccess, refresh: 'new-refresh' });

    expect(received).toBe(newAccess);
    expect(localStorage.getItem('access_token')).toBe(newAccess);
  });

  // ── logout ────────────────────────────────────────────────────────────────

  it('logout — efface tous les tokens du localStorage', () => {
    localStorage.setItem('access_token', 'tok');
    localStorage.setItem('refresh_token', 'ref');
    const spy = spyOn(router, 'navigate');

    service.logout();

    expect(localStorage.getItem('access_token')).toBeNull();
    expect(localStorage.getItem('refresh_token')).toBeNull();
    expect(spy).toHaveBeenCalledWith(['/login'], jasmine.any(Object));
  });

  it('logout — inclut returnUrl dans la navigation', () => {
    const spy = spyOn(router, 'navigate');
    service.logout('/planning/2026-03-09');
    expect(spy).toHaveBeenCalledWith(['/login'], { queryParams: { returnUrl: '/planning/2026-03-09' } });
  });
});
