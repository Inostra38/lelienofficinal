import { ApplicationConfig } from '@angular/core';
import { provideRouter } from '@angular/router';
import { routes } from './app.routes';
import { provideHttpClient, withFetch, withInterceptors } from '@angular/common/http';
import { authInterceptor } from './core/auth/auth.interceptor';
import { provideQuillConfig } from 'ngx-quill';

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes),
    provideHttpClient(
      withFetch(),
      withInterceptors([authInterceptor]),
    ),
    provideQuillConfig({
      formats: [
        'bold', 'italic', 'underline', 'strike',
        'header', 'list',
        'link', 'image',
        'blockquote', 'code-block',
      ],
    }),
  ]
};