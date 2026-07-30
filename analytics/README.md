# Analytics — nowcasting DMTO

Pipeline Python pour estimer, en cours d’année, le **total annuel** de DMTO
par département et par taxe (TDPF, TCAD, DDE, TDAD), à partir des
recouvrements mensuels DGFiP.

Ce dossier est le **laboratoire modèles**. L’application Vue (racine du repo)
ne réentraîne rien : elle consomme un JSON d’artefacts produit ici, puis
**copié** dans le front pour être servi en statique.

## Contenu

| Fichier | Rôle |
| --- | --- |
| `run_nowcast.py` | Comparaison complète des modèles (baseline ratio, Ridge/Elastic Net, CatBoost, LightGBM, XGBoost, blend) avec validation chronologique |
| `export_frontend_artifacts.py` | Entraîne les modèles **portables navigateur** (baseline, Elastic Net, blend) **par taxe**, écrit le JSON, le copie vers le front |
| `requirements.txt` | Dépendances Python |
| `data/` | Cache local des données brutes (non versionné) |
| `outputs/` | Sorties d’évaluation + `artifacts.json` généré |

## Données sources

Les recettes mensuelles sont téléchargées depuis data.gouv.fr :

https://www.data.gouv.fr/api/1/datasets/r/9a8bd034-fdbe-4056-9503-8a3afb03ada4

Au premier run, le fichier est mis en cache dans `data/dmto_raw.json`.

## Installation

```bash
cd analytics
python3 -m pip install -r requirements.txt
```

Sous macOS, LightGBM / XGBoost peuvent nécessiter OpenMP :

```bash
brew install libomp
export DYLD_LIBRARY_PATH="/opt/homebrew/opt/libomp/lib:${DYLD_LIBRARY_PATH:-}"
```

## Génération de `artifacts.json`

### 1. Lancer l’export

Depuis la racine du repo :

```bash
npm run nowcast:export
```

Ou directement :

```bash
cd analytics
python3 export_frontend_artifacts.py
```

### 2. Ce que fait le script

1. Charge (ou télécharge) les données DMTO.
2. Agrège les montants **par département × mois**, pour chaque scope :
   - `TDPF`, `TCAD`, `DDE`, `TDAD`, et `TOTAL`.
3. Construit un jeu supervisé de nowcasting
   `(département, année, mois d’observation) → total annuel de la taxe`.
4. Évalue chronologiquement (ex. train ≤ 2023, val 2024, test 2025) les
   modèles portables :
   - **baseline ratio** historique ;
   - **Elastic Net** (cible en `log1p`) ;
   - **blend** baseline + Elastic Net.
5. Pour chaque mois (1–11), retient le modèle au meilleur MAPE sur le test.
6. Ré-entraîne sur toutes les années complètes et sérialise ratios,
   coefficients Elastic Net, bandes d’erreur empiriques, etc.

### 3. Où est écrit le JSON — puis copie vers le front

Le fichier est d’abord généré **dans analytics** :

```text
analytics/outputs/artifacts.json
```

Puis **copié** dans le dépôt front pour être servi par Vite / le build
statique :

```text
public/nowcast/artifacts.json
```

C’est ce second chemin que l’app Vue charge au runtime
(`fetch('/nowcast/artifacts.json')` dans `src/composables/useDmtoData.js`).
Le front n’importe pas les scripts Python : il n’embarque que ce JSON
précalculé.

En résumé :

```text
analytics/export_frontend_artifacts.py
        │
        ▼
analytics/outputs/artifacts.json     ← artefact « source » côté modèles
        │
        │  copie
        ▼
public/nowcast/artifacts.json        ← consommé par l’app Vue
```

## Comparaison élargie des modèles (optionnel)

Pour le benchmark hors navigateur (CatBoost, LightGBM, XGBoost, etc.) :

```bash
cd analytics
python3 run_nowcast.py
# python3 run_nowcast.py --refresh   # force le retéléchargement des données
```

Les métriques et projections d’exploration sont écrites dans `outputs/`
(`scoreboard.csv`, `metrics_by_month_test.csv`, `projection_current_year.csv`, …).

## Lien avec le front

| Côté analytics | Côté front |
| --- | --- |
| Entraînement / sélection du modèle du mois | Inférence légère dans `src/lib/nowcast.js` |
| `outputs/artifacts.json` puis copie | `public/nowcast/artifacts.json` |
| Cumuls YTD recalculés live depuis data.gouv | Panel : anticipation annuelle, histogramme empilé encaissé / projeté |

Penser à relancer `npm run nowcast:export` après une évolution des données
ou de la logique de modèle, afin de rafraîchir le JSON servi par le front.
