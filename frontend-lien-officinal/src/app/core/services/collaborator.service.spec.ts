import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { CollaboratorService, Collaborator } from './collaborator.service';

describe('CollaboratorService', () => {
  let service: CollaboratorService;
  let httpMock: HttpTestingController;

  // URL de base définie dans ton service (à adapter si tu la changes)
  const apiUrl = 'http://127.0.0.1:8000/api/team/';

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        CollaboratorService,
        // Ces deux lignes sont INDISPENSABLES pour tester des appels API
        provideHttpClient(),
        provideHttpClientTesting() 
      ]
    });
    service = TestBed.inject(CollaboratorService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    // Vérifie qu'il n'y a pas de requêtes "fantômes" qui trainent après chaque test
    httpMock.verify();
  });

  // 1. Test de base : Est-ce que le service se crée ?
  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  // 2. Test de la méthode getTeam()
  it('should retrieve the team list via GET', () => {
    const dummyTeam = [
      { id: 1, first_name: 'Julie', last_name: 'Dupont', role: 'Adjoint' as any },
      { id: 2, first_name: 'Thomas', last_name: 'Martin', role: 'Préparateur' as any }
    ];

    // On lance l'appel
    service.getTeam().subscribe(team => {
      
      expect(team as any).toEqual(dummyTeam);
    });

    // On intercepte la requête HTTP
    const req = httpMock.expectOne(apiUrl);
    
    // On vérifie que c'est bien la bonne méthode
    expect(req.request.method).toBe('GET');

    // On simule la réponse du serveur (Flush)
    req.flush(dummyTeam);
  });

  // 3. Test de la méthode verifyPin()
  it('should verify pin via POST with correct body', () => {
    const mockResponse = { success: true, message: 'PIN Valide' };
    const collabId = 1;
    const pin = '1234';

    // On lance l'appel
    service.verifyPin(collabId, pin).subscribe(response => {
      expect(response.success).toBeTrue();
    });

    // On s'attend à un appel sur l'URL de vérification
    const req = httpMock.expectOne(`${apiUrl}verify-pin/`);
    
    // Vérifications critiques
    expect(req.request.method).toBe('POST');
    // Est-ce qu'on envoie bien le bon JSON ?
    expect(req.request.body).toEqual({
      collaborator_id: collabId,
      pin_code: pin
    });

    // On simule la réponse positive du serveur
    req.flush(mockResponse);
  });
});