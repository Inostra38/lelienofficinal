import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css'
})
export class AppComponent implements OnInit {
  private http = inject(HttpClient);
  
  // Données de test
  categories: any[] = [
    { 
      nom: 'TEST AFFICHAGE', 
      links: [{ titre: 'Si tu vois ça, ça marche', url: '#' }] 
    }
  ];

  ngOnInit() {
    console.log('🚀 Démarrage...');
    this.http.get<any>('http://127.0.0.1:8000/api/categories/')
      .subscribe({
        next: (data) => {
          console.log('✅ Données reçues :', data);
          this.categories = Array.isArray(data) ? data : data.results || [];
        },
        error: (err) => console.error('Erreur API (pas grave pour le test visuel)', err)
      });
  }
}