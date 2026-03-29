import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { PlanningService, TemplateShift, Shift } from './planning.service';

describe('PlanningService', () => {
  let service: PlanningService;
  let httpMock: HttpTestingController;

  const base = 'http://127.0.0.1:8000/api/planning';

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        PlanningService,
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });
    service = TestBed.inject(PlanningService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  // ── bulkReplaceTemplateShifts ─────────────────────────────────────────────

  it('bulkReplaceTemplateShifts — envoie POST et retourne la liste de shifts', () => {
    const mockShifts: TemplateShift[] = [
      {
        id: 1,
        collaborator: { id: 1, first_name: 'Alice', last_name: 'D', color: '#aaa', role: 'Adjoint', weekly_hours: 35 },
        day_of_week: 1,
        start_time: '09:00:00',
        end_time: '17:00:00',
        note: '',
      },
    ];

    service.bulkReplaceTemplateShifts('A', []).subscribe(result => {
      expect(result).toEqual(mockShifts);
    });

    const req = httpMock.expectOne(`${base}/templates/A/bulk-replace/`);
    expect(req.request.method).toBe('POST');
    req.flush(mockShifts);
  });

  it('bulkReplaceTemplateShifts — envoie le tableau de shifts dans le body', () => {
    const dto = [{ collaborator_id: 1, day_of_week: 1, start_time: '09:00', end_time: '17:00' }];

    service.bulkReplaceTemplateShifts('B', dto).subscribe();

    const req = httpMock.expectOne(`${base}/templates/B/bulk-replace/`);
    expect(req.request.body).toEqual(dto);
    req.flush([]);
  });

  // ── pollGenerateTemplate ──────────────────────────────────────────────────

  it('pollGenerateTemplate — retourne le status depuis l\'API', () => {
    const taskId = 'task-abc-123';
    const mockResponse = { status: 'done', message: 'OK', template: null, conversation: [] };

    service.pollGenerateTemplate(taskId).subscribe(result => {
      expect(result.status).toBe('done');
    });

    const req = httpMock.expectOne(`${base}/constraints/generate/${taskId}/`);
    expect(req.request.method).toBe('GET');
    req.flush(mockResponse);
  });

  it('pollGenerateTemplate — status pending est transmis tel quel', () => {
    const taskId = 'task-pending-456';
    const mockPending = { status: 'pending', message: '', template: null, conversation: [] };

    service.pollGenerateTemplate(taskId).subscribe(result => {
      expect(result.status).toBe('pending');
    });

    const req = httpMock.expectOne(`${base}/constraints/generate/${taskId}/`);
    req.flush(mockPending);
  });

  // ── updateShift ───────────────────────────────────────────────────────────

  it('updateShift — envoie PATCH et retourne le shift mis à jour', () => {
    const mockShift = { id: 5 } as Shift;

    service.updateShift(5, { note: 'test' }).subscribe(s => {
      expect(s.id).toBe(5);
    });

    const req = httpMock.expectOne(`${base}/shifts/5/`);
    expect(req.request.method).toBe('PATCH');
    expect(req.request.body).toEqual({ note: 'test' });
    req.flush(mockShift);
  });

  it('updateShift — une erreur 409 est propagée à l\'appelant', () => {
    let errorCaught = false;

    service.updateShift(5, { note: 'conflit' }).subscribe({
      error: err => {
        errorCaught = true;
        expect(err.status).toBe(409);
      },
    });

    const req = httpMock.expectOne(`${base}/shifts/5/`);
    req.flush({ detail: 'Conflict' }, { status: 409, statusText: 'Conflict' });

    expect(errorCaught).toBeTrue();
  });

  // ── getPayeSummary ────────────────────────────────────────────────────────

  it('getPayeSummary — envoie GET avec le param month', () => {
    service.getPayeSummary('2026-03').subscribe();

    const req = httpMock.expectOne(r => r.url.includes('/analytics/paie/'));
    expect(req.request.method).toBe('GET');
    expect(req.request.urlWithParams).toContain('month=2026-03');
    req.flush({ month: '2026-03', jours_ouvres_mois: 22, collaborateurs: [], totaux_salaries: {} });
  });
});
