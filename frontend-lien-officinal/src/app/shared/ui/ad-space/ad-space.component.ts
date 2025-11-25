import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-ad-space',
  standalone: true,
  imports: [CommonModule],
  // 👇 C'est ICI qu'on fait le lien avec le fichier HTML qu'on vient de remplir
  templateUrl: './ad-space.component.html',
  styleUrl: './ad-space.component.css'
})
export class AdSpaceComponent {
  @Input() imageUrl: string | null = null; // L'URL de l'image (si vide -> placeholder)
  @Input() link: string | null = null;     // Le lien au clic
}