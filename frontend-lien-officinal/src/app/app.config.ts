import { ApplicationConfig } from '@angular/core';
import { provideRouter } from '@angular/router';
import { routes } from './app.routes';
import { provideHttpClient, withFetch, withInterceptors } from '@angular/common/http';
import { authInterceptor } from './core/auth/auth.interceptor'; // <-- Import

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes),
    
    // 👇 C'est ici qu'on branche l'intercepteur
    provideHttpClient(
      withFetch(),
      withInterceptors([authInterceptor]) 
    )
  ]
};