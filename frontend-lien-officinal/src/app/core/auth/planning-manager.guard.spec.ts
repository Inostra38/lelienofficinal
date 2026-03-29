import { TestBed } from '@angular/core/testing';
import { Router, provideRouter, ActivatedRouteSnapshot, RouterStateSnapshot } from '@angular/router';
import { planningManagerGuard } from './planning-manager.guard';
import { AuthService } from './auth.service';
import { ToastService } from '../services/toast.service';

describe('planningManagerGuard', () => {
  let authService: jasmine.SpyObj<AuthService>;
  let toastService: jasmine.SpyObj<ToastService>;
  let router: Router;

  beforeEach(() => {
    authService = jasmine.createSpyObj('AuthService', ['canManagePlanning']);
    toastService = jasmine.createSpyObj('ToastService', ['warning']);

    TestBed.configureTestingModule({
      providers: [
        { provide: AuthService, useValue: authService },
        { provide: ToastService, useValue: toastService },
        provideRouter([]),
      ],
    });
    router = TestBed.inject(Router);
  });

  function run(): boolean {
    return TestBed.runInInjectionContext(() =>
      planningManagerGuard({} as ActivatedRouteSnapshot, {} as RouterStateSnapshot) as boolean
    );
  }

  it('can_manage_planning=true → accès accordé (true)', () => {
    authService.canManagePlanning.and.returnValue(true);

    const result = run();

    expect(result).toBeTrue();
    expect(toastService.warning).not.toHaveBeenCalled();
  });

  it('can_manage_planning=false → accès refusé, redirige vers /dashboard', () => {
    authService.canManagePlanning.and.returnValue(false);
    const spy = spyOn(router, 'navigate');

    const result = run();

    expect(result).toBeFalse();
    expect(spy).toHaveBeenCalledWith(['/dashboard']);
  });

  it('can_manage_planning=false → toast d\'avertissement affiché', () => {
    authService.canManagePlanning.and.returnValue(false);
    spyOn(router, 'navigate');

    run();

    expect(toastService.warning).toHaveBeenCalledOnceWith(jasmine.any(String));
  });
});
