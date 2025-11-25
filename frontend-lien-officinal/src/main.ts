import { bootstrapApplication } from '@angular/platform-browser';
import { appConfig } from './app/app.config';

// 👇 AVANT c'était peut-être './app/app'. MAINTENANT c'est :
import { AppComponent } from './app/app.component'; 

bootstrapApplication(AppComponent, appConfig)
  .catch((err) => console.error(err));