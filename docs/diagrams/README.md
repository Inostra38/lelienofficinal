# Sources des diagrammes

Diagrammes [Mermaid](https://mermaid.js.org/) de la documentation. Les mêmes sources
alimentent la version web (Artifact).

| Fichier | Utilisé dans |
|---|---|
| `architecture-systeme.mmd` | [03 — Architecture générale](../03-architecture-generale.md) |
| `erd-coeur.mmd` | [07 — Modèle de données §7.2](../07-modele-de-donnees.md) |
| `erd-ressources.mmd` | [07 §7.3](../07-modele-de-donnees.md) |
| `erd-planning.mmd` | [07 §7.4](../07-modele-de-donnees.md) |
| `erd-qualite.mmd` | [07 §7.5](../07-modele-de-donnees.md) |
| `sequence-auth-pharmacie.mmd` | [08 — Sécurité §8.2](../08-securite-conformite.md) |
| `sequence-auth-collaborateur.mmd` | [08 §8.2](../08-securite-conformite.md) |
| `sequence-auth-admin.mmd` | [08 §8.2](../08-securite-conformite.md) |
| `sequence-refresh-401.mmd` | [05 — Front-end §5.4](../05-frontend-angular.md) |
| `cicd-pipeline.mmd` | [10 — Déploiement §10.4](../10-deploiement-exploitation.md) |
| `billing-lifecycle.mmd` | [09 — Modules transverses §9.1](../09-modules-transverses.md) |

Pour régénérer une image : `npx @mermaid-js/mermaid-cli -i fichier.mmd -o fichier.svg`.
