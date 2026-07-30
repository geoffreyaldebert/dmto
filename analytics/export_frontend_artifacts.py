#!/usr/bin/env python3
"""
Exporte les artefacts nowcast consommables par l'app Vue
vers ../public/nowcast/artifacts.json

Un modèle portable (baseline / ElasticNet / blend) est entraîné
**par taxe** : TDPF, TCAD, DDE, TDAD, ainsi qu'un TOTAL agrégé.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from run_nowcast import (  # noqa: E402
    CACHE_PATH,
    DATA_URL,
    FEATURE_CAT,
    FEATURE_NUM,
    HistoricalRatioBaseline,
    OUT_DIR,
    build_supervised,
    chronological_split,
    enrich_features,
    fetch_raw,
    make_linear,
    mape,
    metrics,
    monthly_totals,
    predict_positive,
    prepare_xy,
)

PUBLIC = ROOT.parent / "public" / "nowcast"

SCOPES = [
    {
        "id": "TDPF",
        "label": "Taxe départementale de publicité foncière",
        "beneficiary": "Département",
        "categorie": "TDPF",
    },
    {
        "id": "TCAD",
        "label": "Taxe communale additionnelle",
        "beneficiary": "Communes",
        "categorie": "TCAD",
    },
    {
        "id": "DDE",
        "label": "Droits départementaux d'enregistrement",
        "beneficiary": "Département",
        "categorie": "DDE",
    },
    {
        "id": "TDAD",
        "label": "Taxe départementale additionnelle",
        "beneficiary": "Département",
        "categorie": "TDAD",
    },
    {
        "id": "TOTAL",
        "label": "Total DMTO",
        "beneficiary": "Ensemble",
        "categorie": None,
    },
]


def export_baseline(baseline: HistoricalRatioBaseline) -> dict:
    dept_month = {
        f"{dept}|{int(month)}": float(share)
        for (dept, month), share in baseline.ratios_.items()
        if np.isfinite(share)
    }
    national = {
        str(int(month)): float(share)
        for month, share in baseline.national_.items()
        if np.isfinite(share)
    }
    return {"dept_month_share": dept_month, "national_share": national}


def export_elasticnet(pipe, feature_num: list[str], feature_cat: list[str]) -> dict:
    pre = pipe.named_steps["pre"]
    est = pipe.named_steps["est"]
    num = pre.named_transformers_["num"]
    cat = pre.named_transformers_["cat"]
    return {
        "feature_num": feature_num,
        "feature_cat": feature_cat,
        "num_mean": num.mean_.tolist(),
        "num_scale": num.scale_.tolist(),
        "categories": [c.tolist() for c in cat.categories_],
        "coef": est.coef_.tolist(),
        "intercept": float(est.intercept_),
        "target": "log1p_annual",
    }


def rel_error_quantiles(y_true, y_pred, q=(0.1, 0.9)) -> dict:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    rel = (y_pred - y_true) / np.clip(y_true, 1.0, None)
    lo, hi = np.quantile(rel, q)
    return {"rel_q10": float(lo), "rel_q90": float(hi)}


def fit_scope(supervised: pd.DataFrame, val_year: int, test_year: int) -> dict | None:
    if supervised.empty or supervised["dept"].nunique() < 5:
        return None

    available = sorted(supervised["year"].unique())
    if val_year not in available or test_year not in available:
        if len(available) < 2:
            return None
        test_year = available[-1]
        val_year = available[-2]

    train, val, test = chronological_split(supervised, val_year, test_year)
    if train.empty or val.empty or test.empty:
        return None

    baseline_tr = HistoricalRatioBaseline().fit(train)
    train_e = enrich_features(train, baseline_tr)
    val_e = enrich_features(val, baseline_tr)
    test_e = enrich_features(test, baseline_tr)

    X_train, y_train = prepare_xy(train_e)
    X_val, y_val = prepare_xy(val_e)
    X_test, y_test = prepare_xy(test_e)

    pipe = make_linear("elasticnet")
    pipe.fit(X_train, np.log1p(y_train))

    results = {
        "baseline_ratio": {
            "val": baseline_tr.predict(val_e),
            "test": baseline_tr.predict(test_e),
        },
        "elasticnet": {
            "val": predict_positive(pipe.predict(X_val), val_e["cumul"].to_numpy()),
            "test": predict_positive(pipe.predict(X_test), test_e["cumul"].to_numpy()),
        },
    }
    results["blend_baseline_elasticnet"] = {
        "val": 0.5 * results["baseline_ratio"]["val"]
        + 0.5 * results["elasticnet"]["val"],
        "test": 0.5 * results["baseline_ratio"]["test"]
        + 0.5 * results["elasticnet"]["test"],
    }

    month_winners = {}
    for m in range(1, 12):
        mask = (test_e["month_obs"] == m).to_numpy()
        if mask.sum() == 0:
            month_winners[str(m)] = "baseline_ratio"
            continue
        best_name, best_mape = "baseline_ratio", np.inf
        for name, preds in results.items():
            mp = mape(y_test.to_numpy()[mask], preds["test"][mask])
            if np.isfinite(mp) and mp < best_mape:
                best_mape, best_name = mp, name
        month_winners[str(m)] = best_name

    intervals = {
        name: rel_error_quantiles(y_val, preds["val"])
        for name, preds in results.items()
    }

    scoreboard = []
    for name, preds in results.items():
        scoreboard.append({"model": name, "split": "val", **metrics(y_val, preds["val"])})
        scoreboard.append(
            {"model": name, "split": "test", **metrics(y_test, preds["test"])}
        )

    baseline_full = HistoricalRatioBaseline().fit(supervised)
    full_e = enrich_features(supervised, baseline_full)
    X_full, y_full = prepare_xy(full_e)
    pipe_full = make_linear("elasticnet")
    pipe_full.fit(X_full, np.log1p(y_full))

    return {
        "eval": {
            "val_year": int(val_year),
            "test_year": int(test_year),
            "scoreboard": scoreboard,
            "n_train": int(len(train)),
            "n_val": int(len(val)),
            "n_test": int(len(test)),
        },
        "model_by_month": month_winners,
        "baseline": export_baseline(baseline_full),
        "elasticnet": export_elasticnet(pipe_full, FEATURE_NUM, FEATURE_CAT),
        "blend": {"weight_baseline": 0.5, "weight_ml": 0.5},
        "intervals": intervals,
    }


def main() -> None:
    PUBLIC.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    raw = fetch_raw(DATA_URL, CACHE_PATH, force=False)
    monthly_total = monthly_totals(raw)
    available_years = sorted(
        build_supervised(monthly_total)[0]["year"].unique()
    )
    test_year = int(available_years[-1])
    val_year = int(available_years[-2])
    print(f"→ split de référence train≤{val_year - 1} / val {val_year} / test {test_year}")

    scopes_out = {}
    score_rows = []

    for scope in SCOPES:
        sid = scope["id"]
        print(f"→ scope {sid}…")
        monthly = (
            monthly_total
            if scope["categorie"] is None
            else monthly_totals(raw, categorie=scope["categorie"])
        )
        if monthly.empty:
            print(f"  ! aucune donnée pour {sid}")
            continue

        supervised, _, _ = build_supervised(
            monthly,
            completeness_monthly=monthly_total,
        )
        fitted = fit_scope(supervised, val_year, test_year)
        if fitted is None:
            print(f"  ! entraînement impossible pour {sid}")
            continue

        scopes_out[sid] = {
            "id": sid,
            "label": scope["label"],
            "beneficiary": scope["beneficiary"],
            **fitted,
        }
        for row in fitted["eval"]["scoreboard"]:
            score_rows.append({"scope": sid, **row})
        print(
            f"  ok — test MAPE baseline "
            f"{next(r['MAPE_%'] for r in fitted['eval']['scoreboard'] if r['model']=='baseline_ratio' and r['split']=='test'):.1f}%"
        )

    current_year = int(monthly_total["year"].max())
    current_month = int(
        monthly_total.loc[monthly_total["year"] == current_year, "month"].max()
    )

    artifacts = {
        "version": 2,
        "generated_from": DATA_URL,
        "current_data_year": current_year,
        "current_data_month": current_month,
        "scope_order": [s["id"] for s in SCOPES if s["id"] in scopes_out],
        "scopes": scopes_out,
        # rétrocompat : TOTAL au premier niveau si présent
        **(
            {
                "model_by_month": scopes_out["TOTAL"]["model_by_month"],
                "baseline": scopes_out["TOTAL"]["baseline"],
                "elasticnet": scopes_out["TOTAL"]["elasticnet"],
                "blend": scopes_out["TOTAL"]["blend"],
                "intervals": scopes_out["TOTAL"]["intervals"],
            }
            if "TOTAL" in scopes_out
            else {}
        ),
        "notes": (
            "version 2 : un modèle par taxe (TDPF/TCAD/DDE/TDAD) + TOTAL. "
            "TDPF = département, TCAD = communes. "
            "Projection client = cumul YTD de la taxe ÷ modèle du mois."
        ),
    }

    if score_rows:
        pd.DataFrame(score_rows).to_csv(
            OUT_DIR / "frontend_scoreboard_by_scope.csv", index=False
        )

    payload = json.dumps(artifacts, ensure_ascii=False)
    analytics_out = OUT_DIR / "artifacts.json"
    analytics_out.write_text(payload, encoding="utf-8")
    print(f"✓ écrit {analytics_out} ({len(scopes_out)} scopes)")

    # Copie vers le front (dossier public servi par Vite)
    PUBLIC.mkdir(parents=True, exist_ok=True)
    front_out = PUBLIC / "artifacts.json"
    front_out.write_text(payload, encoding="utf-8")
    print(f"✓ copié vers le front → {front_out}")
    print(f"données courantes : {current_year}-{current_month:02d}")


if __name__ == "__main__":
    main()
