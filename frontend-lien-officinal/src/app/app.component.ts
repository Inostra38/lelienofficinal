import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet], // <--- C'est la clé du routing
  template: `<router-outlet></router-outlet>`, // <--- La zone d'affichage dynamique
  styles: []
})
export class AppComponent {}