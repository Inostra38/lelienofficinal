import { TestBed } from '@angular/core/testing';
import { Router, provideRouter, ActivatedRouteSnapshot, RouterStateSnapshot } from '@angular/router';
import { authGuard } from './auth.guard';
import { AuthService } from './auth.service';

function makeState(url: string): RouterStateSnapshot {
  return { url } as RouterStateSnapshot;
}

describe('authGuard', () => {
  let authService: jasmine.SpyObj<AuthService>;
  let router: Router;

  beforeEach(() => {
    authService = jasmine.createSpyObj('AuthService', ['isAuthenticated', 'isOnboardingCompleted']);

    TestBed.configureTestingModule({
      providers: [
        { provide: AuthService, useValue: authService },
        provideRouter([]),
      ],
    });
    router = TestBed.inject(Router);
  });

  function run(url = '/dashboard'): boolean {
    return TestBed.runInInjectionContext(() =>
      authGuard({} as ActivatedRouteSnapshot, makeState(url)) as boolean
    );
  }

  it('non connecté → redirige vers /login avec returnUrl', () => {
    authService.isAuthenticated.and.returnValue(false);
    const spy = spyOn(router, 'navigate');

    const result = run('/planning/2026-03-09');

    expect(result).toBeFalse();
    expect(spy).toHaveBeenCalledWith(['/login'], { queryParams: { returnUrl: '/planning/2026-03-09' } });
  });

  it('connecté + onboarding terminé → accès accordé (true)', () => {
    authService.isAuthenticated.and.returnValue(true);
    authService.isOnboardingCompleted.and.returnValue(true);

    const result = run('/dashboard');
    expect(result).toBeTrue();
  });

  it('connecté + onboarding non terminé → redirige vers /onboarding', () => {
    authService.isAuthenticated.and.returnValue(true);
    authService.isOnboardingCompleted.and.returnValue(false);
    const spy = spyOn(router, 'navigate');

    const result = run('/dashboard');

    expect(result).toBeFalse();
    expect(spy).toHaveBeenCalledWith(['/onboarding']);
  });

  it('connecté + onboarding non terminé + url déjà /onboarding → accès accordé', () => {
    authService.isAuthenticated.and.returnValue(true);
    authService.isOnboardingCompleted.and.returnValue(false);

    const result = run('/onboarding');
    expect(result).toBeTrue();
  });
});
