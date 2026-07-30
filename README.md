# DMTO — visualisation départementale

Application Vue 3 pour explorer les **droits de mutation à titre onéreux (DMTO)** par département.

## Fonctionnalités

- Panel gauche : présentation, anticipation annuelle par taxe, tableaux, graphiques
- Carte MapLibre : chloropleth des départements
- Graphiques ECharts : évolution mensuelle + histogramme annuel (encaissé / projeté)
- Nowcasting (ratio historique / Elastic Net) via artefacts générés dans `analytics/`

## Données

Chargées en direct depuis data.gouv.fr :

https://www.data.gouv.fr/api/1/datasets/r/9a8bd034-fdbe-4056-9503-8a3afb03ada4

## Démarrage

```bash
npm install
npm run dev
```

Build production (`dist/`) :

```bash
npm run build
```

Prévisualiser le build comme sur GitHub Pages :

```bash
npm run preview
```

## Publication GitHub Pages

Le projet est configuré pour être servi sous
`https://<user>.github.io/dmto/` (`base: '/dmto/'` dans Vite).

1. Pousser le repo sur GitHub (nom recommandé : `dmto`).
2. Settings → Pages → Source : **GitHub Actions**.
3. Au push sur `main` / `master`, le workflow
   [`.github/workflows/deploy-pages.yml`](.github/workflows/deploy-pages.yml)
   exécute `npm ci && npm run build` et publie le dossier **`dist`**.

Le build copie aussi `index.html` → `404.html` pour que les routes SPA
(`/methode`, etc.) fonctionnent sur Pages.

Assets publics (`departements.geojson`, `nowcast/artifacts.json`) sont
préfixés avec le base `/dmto/`.

Pour régénérer les artefacts de projection avant un déploiement :

```bash
npm run nowcast:export
npm run build
```

Voir aussi [`analytics/README.md`](./analytics/README.md).

## Licence

Ce projet est publié sous licence [MIT](./LICENSE) : composants, code, méthodes et visualisations peuvent être librement réutilisés.
