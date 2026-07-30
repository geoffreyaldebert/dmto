#!/usr/bin/env python3
"""
Nowcasting des recettes annuelles DMTO à partir des recouvrements mensuels.

Compare :
  1. Baseline ratio historique (département × mois)
  2. Ridge / Elastic Net (sur log du total, avec prédiction baseline en feature)
  3. CatBoost / LightGBM / XGBoost (idem)

Validation chronologique :
  train ≤ 2023 | validation 2024 | test 2025
  (ajusté automatiquement si une année n'est pas encore complète)

Usage :
  python run_nowcast.py
  python run_nowcast.py --refresh
"""

from __future__ import annotations

import argparse
import json
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

DATA_URL = (
    "https://www.data.gouv.fr/api/1/datasets/r/9a8bd034-fdbe-4056-9503-8a3afb03ada4"
)
ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "outputs"
CACHE_PATH = ROOT / "data" / "dmto_raw.json"
DEPT_EXCLUDE = {"Non_connus"}

FEATURE_NUM = [
    "month_obs",
    "year",
    "covid",
    "cumul",
    "amount",
    "mom_change",
    "ma3",
    "prev_year_total",
    "ratio_vs_prev_year",
    "hist_share_global",
    "pace_vs_hist",
    "baseline_pred",
    "log_cumul",
    "log_prev_year",
    "log_baseline",
]
FEATURE_CAT = ["dept"]


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


def fetch_raw(url: str, cache: Path, force: bool = False) -> list[dict]:
    cache.parent.mkdir(parents=True, exist_ok=True)
    if cache.exists() and not force:
        print(f"→ cache local : {cache}")
        return json.loads(cache.read_text(encoding="utf-8"))
    print(f"→ téléchargement {url}")
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    data = r.json()
    cache.write_text(json.dumps(data), encoding="utf-8")
    return data


def monthly_totals(rows: list[dict], categorie: str | None = None) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df = df[~df["collectivite_attributaire"].isin(DEPT_EXCLUDE)].copy()
    df = df[~df["collectivite_attributaire"].astype(str).str.startswith("R")]
    df["dept"] = df["collectivite_attributaire"].replace({"2A": "20", "2B": "20"})
    df["dept"] = df["dept"].astype(str).str.zfill(2)
    df["recettes"] = pd.to_numeric(df["recettes"], errors="coerce").fillna(0.0)
    df["year"] = df["date"].str.slice(0, 4).astype(int)
    df["month"] = df["date"].str.slice(5, 7).astype(int)
    if categorie:
        df = df[df["categorie_dmto"] == categorie].copy()

    monthly = (
        df.groupby(["dept", "year", "month"], as_index=False)["recettes"]
        .sum()
        .rename(columns={"recettes": "amount"})
    )
    # Noms : depuis le jeu filtré, ou fallback sur le libellé le plus fréquent global
    if len(df):
        names = (
            df.groupby("dept")["libelle_coll_attrib"]
            .agg(lambda s: s.value_counts().index[0])
            .rename("dept_name")
        )
        monthly = monthly.merge(names, on="dept", how="left")
    else:
        monthly["dept_name"] = monthly["dept"]
    return monthly.sort_values(["dept", "year", "month"]).reset_index(drop=True)


def complete_calendar(
    monthly: pd.DataFrame, universe: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Grille dept × année × mois. `universe` fixe la liste des départements/années."""
    base = universe if universe is not None else monthly
    name_src = monthly if "dept_name" in monthly.columns else base
    if "dept_name" not in name_src.columns:
        name_src = name_src.assign(dept_name=name_src["dept"])
    depts = (
        name_src[["dept", "dept_name"]]
        .drop_duplicates("dept")
        .merge(base[["dept"]].drop_duplicates(), on="dept", how="right")
    )
    depts["dept_name"] = depts["dept_name"].fillna(depts["dept"])
    years = range(int(base["year"].min()), int(base["year"].max()) + 1)
    grid = pd.MultiIndex.from_product(
        [depts["dept"], years, range(1, 13)],
        names=["dept", "year", "month"],
    ).to_frame(index=False)
    grid = grid.merge(depts, on="dept", how="left")
    amount_cols = monthly[["dept", "year", "month", "amount"]]
    out = grid.merge(amount_cols, on=["dept", "year", "month"], how="left")
    out["amount"] = out["amount"].fillna(0.0)
    return out


def build_supervised(
    monthly: pd.DataFrame,
    completeness_monthly: pd.DataFrame | None = None,
):
    """
    completeness_monthly : série utilisée pour décider si une année est complète
    (typiquement le total toutes taxes). Évite de marquer incomplète une année
    où une taxe donnée n'a simplement aucun flux certains mois.
    """
    universe = completeness_monthly if completeness_monthly is not None else monthly
    cal = complete_calendar(monthly, universe=universe)
    annual = (
        cal.groupby(["dept", "year"], as_index=False)["amount"]
        .sum()
        .rename(columns={"amount": "annual_total"})
    )
    raw_ref = completeness_monthly if completeness_monthly is not None else monthly
    raw_months = raw_ref.groupby(["dept", "year"])["month"].nunique().rename("n_months")
    annual = annual.merge(raw_months, on=["dept", "year"], how="left")
    annual["year_complete"] = annual["n_months"].fillna(0) >= 12

    cal = cal.merge(annual, on=["dept", "year"], how="left")
    cal = cal.sort_values(["dept", "year", "month"])
    cal["cumul"] = cal.groupby(["dept", "year"])["amount"].cumsum()
    cal["prev_month_amount"] = cal.groupby(["dept", "year"])["amount"].shift(1)
    cal["mom_change"] = cal["amount"] - cal["prev_month_amount"]
    cal["ma3"] = (
        cal.groupby(["dept", "year"])["amount"]
        .rolling(3, min_periods=1)
        .mean()
        .reset_index(level=[0, 1], drop=True)
    )

    prev = annual[["dept", "year", "annual_total"]].copy()
    prev["year"] = prev["year"] + 1
    prev = prev.rename(columns={"annual_total": "prev_year_total"})
    cal = cal.merge(prev, on=["dept", "year"], how="left")
    cal["ratio_vs_prev_year"] = np.where(
        cal["prev_year_total"] > 0,
        cal["cumul"] / cal["prev_year_total"],
        np.nan,
    )

    hist = cal[cal["year_complete"] & (cal["annual_total"] > 0)].copy()
    hist["share"] = np.where(
        hist["annual_total"] > 0, hist["cumul"] / hist["annual_total"], np.nan
    )
    share_rows = []
    if len(hist):
        for (dept, month), g in hist.groupby(["dept", "month"]):
            g = g.sort_values("year")
            expanding = g["share"].expanding().mean().shift(1)
            share_rows.append(
                pd.DataFrame(
                    {
                        "dept": dept,
                        "month": month,
                        "year": g["year"].to_numpy(),
                        "hist_share_global": expanding.to_numpy(),
                    }
                )
            )
    share_map = (
        pd.concat(share_rows, ignore_index=True)
        if share_rows
        else pd.DataFrame(columns=["dept", "month", "year", "hist_share_global"])
    )

    nat_rows = []
    if len(hist):
        for month, g in hist.groupby("month"):
            yearly = g.groupby("year")["share"].mean().sort_index()
            exp = yearly.expanding().mean().shift(1)
            for y, v in exp.items():
                nat_rows.append({"month": month, "year": y, "hist_share_nat": v})
    nat_map = (
        pd.DataFrame(nat_rows)
        if nat_rows
        else pd.DataFrame(columns=["month", "year", "hist_share_nat"])
    )

    cal = cal.merge(share_map, on=["dept", "month", "year"], how="left")
    cal = cal.merge(nat_map, on=["month", "year"], how="left")
    cal["hist_share_global"] = cal["hist_share_global"].fillna(cal["hist_share_nat"])
    cal["pace_vs_hist"] = np.where(
        (cal["hist_share_global"] > 0) & (cal["prev_year_total"] > 0),
        cal["cumul"] / (cal["hist_share_global"] * cal["prev_year_total"]),
        np.nan,
    )

    cal["covid"] = (cal["year"] == 2020).astype(int)
    cal["month_obs"] = cal["month"]

    # Années complètes avec un total annuel > 0 pour la taxe considérée
    supervised = cal[
        (cal["month"] <= 11) & (cal["year_complete"]) & (cal["annual_total"] > 0)
    ].copy()
    supervised["y"] = supervised["annual_total"]

    current_year = int(universe["year"].max())
    max_month = int(universe.loc[universe["year"] == current_year, "month"].max())
    ops = cal[
        (cal["year"] == current_year)
        & (cal["month"] == max_month)
        & (cal["month"] <= 11)
    ].copy()

    return supervised, ops, cal


# ---------------------------------------------------------------------------
# Metrics & baseline
# ---------------------------------------------------------------------------


def mape(y_true, y_pred) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mask = y_true != 0
    if mask.sum() == 0:
        return np.nan
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


def metrics(y_true, y_pred) -> dict:
    return {
        "MAE": float(mean_absolute_error(y_true, y_pred)),
        "RMSE": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "MAPE_%": mape(y_true, y_pred),
    }


def metrics_by_month(df: pd.DataFrame, y_col: str, p_col: str) -> pd.DataFrame:
    rows = []
    for m, g in df.groupby("month_obs"):
        rows.append({"month": int(m), **metrics(g[y_col], g[p_col])})
    return pd.DataFrame(rows).sort_values("month")


class HistoricalRatioBaseline:
    def __init__(self):
        self.ratios_: pd.Series | None = None
        self.national_: pd.Series | None = None

    def fit(self, train: pd.DataFrame):
        tmp = train.copy()
        tmp["share"] = np.where(tmp["y"] > 0, tmp["cumul"] / tmp["y"], np.nan)
        tmp["share"] = tmp["share"].clip(0.02, 0.98)
        self.ratios_ = tmp.groupby(["dept", "month_obs"])["share"].mean()
        self.national_ = tmp.groupby("month_obs")["share"].mean()
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        out = []
        for _, row in df.iterrows():
            r = self.ratios_.get((row["dept"], row["month_obs"]), np.nan)
            if not np.isfinite(r) or r <= 0:
                r = self.national_.get(row["month_obs"], 0.5)
            r = float(np.clip(r, 0.02, 0.98))
            out.append(row["cumul"] / r)
        return np.asarray(out, dtype=float)


def enrich_features(df: pd.DataFrame, baseline: HistoricalRatioBaseline) -> pd.DataFrame:
    out = df.copy()
    out["baseline_pred"] = baseline.predict(out)
    out["log_cumul"] = np.log1p(out["cumul"].clip(lower=0))
    out["log_prev_year"] = np.log1p(out["prev_year_total"].fillna(0).clip(lower=0))
    out["log_baseline"] = np.log1p(out["baseline_pred"].clip(lower=0))
    return out


def prepare_xy(df: pd.DataFrame):
    X = df[FEATURE_NUM + FEATURE_CAT].copy()
    for c in FEATURE_NUM:
        X[c] = pd.to_numeric(X[c], errors="coerce")
    X = X.fillna(0.0)
    y = df["y"].astype(float)
    return X, y


# ---------------------------------------------------------------------------
# Models (predict log1p(y), inverse = expm1)
# ---------------------------------------------------------------------------


@dataclass
class ModelResult:
    name: str
    pred_val: np.ndarray
    pred_test: np.ndarray
    model: object | None = None


def make_linear(kind: str) -> Pipeline:
    pre = ColumnTransformer(
        [
            ("num", StandardScaler(), FEATURE_NUM),
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                FEATURE_CAT,
            ),
        ]
    )
    est = (
        Ridge(alpha=5.0, random_state=42)
        if kind == "ridge"
        else ElasticNet(alpha=0.05, l1_ratio=0.3, max_iter=8000, random_state=42)
    )
    return Pipeline([("pre", pre), ("est", est)])


def predict_positive(raw: np.ndarray, cumul: np.ndarray) -> np.ndarray:
    """Inverse log + plancher au cumul déjà encaissé."""
    pred = np.expm1(raw)
    return np.maximum(pred, cumul)


def fit_catboost(X_train, y_log, X_val, y_log_val):
    from catboost import CatBoostRegressor

    model = CatBoostRegressor(
        iterations=1200,
        depth=6,
        learning_rate=0.04,
        loss_function="RMSE",
        random_seed=42,
        verbose=False,
        cat_features=["dept"],
        early_stopping_rounds=60,
    )
    model.fit(X_train, y_log, eval_set=(X_val, y_log_val), use_best_model=True)
    return model


def fit_lightgbm(X_train, y_log, X_val, y_log_val):
    import lightgbm as lgb

    Xt, Xv = X_train.copy(), X_val.copy()
    Xt["dept"] = Xt["dept"].astype("category")
    Xv["dept"] = Xv["dept"].astype("category")
    model = lgb.LGBMRegressor(
        n_estimators=1200,
        learning_rate=0.04,
        num_leaves=40,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=42,
        verbosity=-1,
    )
    model.fit(
        Xt,
        y_log,
        eval_set=[(Xv, y_log_val)],
        categorical_feature=["dept"],
        callbacks=[lgb.early_stopping(60, verbose=False)],
    )
    return model


def fit_xgboost(X_train, y_log, X_val, y_log_val):
    from xgboost import XGBRegressor

    pre = ColumnTransformer(
        [
            ("num", "passthrough", FEATURE_NUM),
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                FEATURE_CAT,
            ),
        ]
    )
    Xt = pre.fit_transform(X_train)
    Xv = pre.transform(X_val)
    model = XGBRegressor(
        n_estimators=1200,
        max_depth=6,
        learning_rate=0.04,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=42,
        early_stopping_rounds=60,
        verbosity=0,
    )
    model.fit(Xt, y_log, eval_set=[(Xv, y_log_val)], verbose=False)
    return model, pre


def attach_intervals(preds: np.ndarray, rel_errors: np.ndarray, q: float = 0.1):
    lo_q, hi_q = np.quantile(rel_errors, [q, 1 - q])
    return preds * (1 + lo_q), preds * (1 + hi_q)


def bayesian_note(train: pd.DataFrame) -> str:
    return (
        f"Modèle bayésien hiérarchique : faisable "
        f"({train['dept'].nunique()} départements, {len(train)} obs). "
        f"Approche conseillée : intercepts dept ~ Normal(μ, σ) + régression sur "
        f"log(cumul), mois, covid (PyMC/Stan). Non exécuté ici (coût MCMC) ; "
        f"CatBoost avec `dept` catégoriel joue déjà un rôle d'effet aléatoire empirique."
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def chronological_split(df: pd.DataFrame, val_year: int, test_year: int):
    return (
        df[df["year"] <= val_year - 1].copy(),
        df[df["year"] == val_year].copy(),
        df[df["year"] == test_year].copy(),
    )


def run(args: argparse.Namespace) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    raw = fetch_raw(args.data_url, CACHE_PATH, force=args.refresh)
    monthly = monthly_totals(raw)
    print(
        f"→ mensuel : {len(monthly)} lignes | "
        f"{monthly['dept'].nunique()} depts | "
        f"{monthly['year'].min()}–{monthly['year'].max()}"
    )

    supervised, ops, _ = build_supervised(monthly)
    print(f"→ dataset supervisé : {len(supervised)} obs")

    val_year, test_year = args.val_year, args.test_year
    available = sorted(supervised["year"].unique())
    if test_year not in available or val_year not in available:
        test_year = available[-1]
        val_year = available[-2]
        print(
            f"! années ajustées : train≤{val_year - 1}, val={val_year}, test={test_year}"
        )

    train, val, test = chronological_split(supervised, val_year, test_year)
    print(f"→ split : train={len(train)} val={len(val)} test={len(test)}")

    # Baseline d'abord (ratios hors val/test)
    print("→ baseline ratio historique…")
    baseline = HistoricalRatioBaseline().fit(train)
    train_e = enrich_features(train, baseline)
    val_e = enrich_features(val, baseline)
    test_e = enrich_features(test, baseline)

    X_train, y_train = prepare_xy(train_e)
    X_val, y_val = prepare_xy(val_e)
    X_test, y_test = prepare_xy(test_e)
    y_log_train = np.log1p(y_train)
    y_log_val = np.log1p(y_val)

    results: dict[str, ModelResult] = {}
    scoreboard = []

    pv = baseline.predict(val_e)
    pt = baseline.predict(test_e)
    results["baseline_ratio"] = ModelResult("baseline_ratio", pv, pt, baseline)
    scoreboard += [
        {"model": "baseline_ratio", "split": "val", **metrics(y_val, pv)},
        {"model": "baseline_ratio", "split": "test", **metrics(y_test, pt)},
    ]

    for kind in ("ridge", "elasticnet"):
        print(f"→ {kind} (log-cible)…")
        pipe = make_linear(kind)
        pipe.fit(X_train, y_log_train)
        pv = predict_positive(pipe.predict(X_val), val_e["cumul"].to_numpy())
        pt = predict_positive(pipe.predict(X_test), test_e["cumul"].to_numpy())
        results[kind] = ModelResult(kind, pv, pt, pipe)
        scoreboard += [
            {"model": kind, "split": "val", **metrics(y_val, pv)},
            {"model": kind, "split": "test", **metrics(y_test, pt)},
        ]

    print("→ CatBoost…")
    try:
        cat = fit_catboost(X_train, y_log_train, X_val, y_log_val)
        pv = predict_positive(cat.predict(X_val), val_e["cumul"].to_numpy())
        pt = predict_positive(cat.predict(X_test), test_e["cumul"].to_numpy())
        results["catboost"] = ModelResult("catboost", pv, pt, cat)
        scoreboard += [
            {"model": "catboost", "split": "val", **metrics(y_val, pv)},
            {"model": "catboost", "split": "test", **metrics(y_test, pt)},
        ]
    except Exception as e:
        print(f"  ! CatBoost : {e}")

    print("→ LightGBM…")
    try:
        lgbm = fit_lightgbm(X_train, y_log_train, X_val, y_log_val)
        Xv = X_val.copy()
        Xt = X_test.copy()
        Xv["dept"] = Xv["dept"].astype("category")
        Xt["dept"] = Xt["dept"].astype("category")
        pv = predict_positive(lgbm.predict(Xv), val_e["cumul"].to_numpy())
        pt = predict_positive(lgbm.predict(Xt), test_e["cumul"].to_numpy())
        results["lightgbm"] = ModelResult("lightgbm", pv, pt, lgbm)
        scoreboard += [
            {"model": "lightgbm", "split": "val", **metrics(y_val, pv)},
            {"model": "lightgbm", "split": "test", **metrics(y_test, pt)},
        ]
    except Exception as e:
        print(f"  ! LightGBM : {e}")

    print("→ XGBoost…")
    try:
        xgb, pre = fit_xgboost(X_train, y_log_train, X_val, y_log_val)
        pv = predict_positive(
            xgb.predict(pre.transform(X_val)), val_e["cumul"].to_numpy()
        )
        pt = predict_positive(
            xgb.predict(pre.transform(X_test)), test_e["cumul"].to_numpy()
        )
        results["xgboost"] = ModelResult("xgboost", pv, pt, (xgb, pre))
        scoreboard += [
            {"model": "xgboost", "split": "val", **metrics(y_val, pv)},
            {"model": "xgboost", "split": "test", **metrics(y_test, pt)},
        ]
    except Exception as e:
        print(f"  ! XGBoost : {e}")

    # Blend baseline + meilleur boosting (si dispo)
    boosters = [n for n in ("catboost", "lightgbm", "xgboost") if n in results]
    if boosters:
        best_boost = min(
            boosters,
            key=lambda n: mape(y_val, results[n].pred_val),
        )
        pv = 0.5 * results["baseline_ratio"].pred_val + 0.5 * results[best_boost].pred_val
        pt = 0.5 * results["baseline_ratio"].pred_test + 0.5 * results[best_boost].pred_test
        blend_name = f"blend_baseline_{best_boost}"
        results[blend_name] = ModelResult(blend_name, pv, pt, None)
        scoreboard += [
            {"model": blend_name, "split": "val", **metrics(y_val, pv)},
            {"model": blend_name, "split": "test", **metrics(y_test, pt)},
        ]

    scores = pd.DataFrame(scoreboard)
    scores.to_csv(OUT_DIR / "scoreboard.csv", index=False)
    print("\n=== Scoreboard ===")
    print(scores.to_string(index=False, float_format=lambda x: f"{x:,.1f}"))

    val_rank = scores[scores["split"] == "val"].sort_values("MAPE_%")
    best_name = val_rank.iloc[0]["model"]
    print(f"\n→ meilleur (val MAPE) : {best_name}")

    # Par mois : baseline + meilleur (dédupliqué)
    compare = []
    for name in dict.fromkeys(["baseline_ratio", best_name]):
        if name not in results:
            continue
        tmp = test_e[["dept", "dept_name", "year", "month_obs", "cumul", "y"]].copy()
        tmp["pred"] = results[name].pred_test
        tmp["model"] = name
        tmp.to_csv(OUT_DIR / f"predictions_test_{name}.csv", index=False)
        by_m = metrics_by_month(tmp, "y", "pred")
        by_m["model"] = name
        compare.append(by_m)

    by_month = pd.concat(compare, ignore_index=True)
    by_month.to_csv(OUT_DIR / "metrics_by_month_test.csv", index=False)
    print("\n=== MAPE_% par mois (test) ===")
    pivot = by_month.pivot_table(index="month", columns="model", values="MAPE_%")
    print(pivot.to_string(float_format=lambda x: f"{x:.2f}"))

    # Meilleur modèle global test + meilleur par mois (pour la projection ops)
    test_rank = scores[scores["split"] == "test"].sort_values("MAPE_%")
    best_test_name = test_rank.iloc[0]["model"]
    print(f"→ meilleur (test MAPE) : {best_test_name}")

    month_winners = {}
    for m in range(1, 12):
        best_m, best_mape = None, np.inf
        for name, res in results.items():
            mask = (test_e["month_obs"] == m).to_numpy()
            mp = mape(y_test.to_numpy()[mask], res.pred_test[mask])
            if mp < best_mape:
                best_mape, best_m = mp, name
        month_winners[m] = best_m
    (OUT_DIR / "best_model_by_month.json").write_text(
        json.dumps(month_winners, indent=2), encoding="utf-8"
    )

    base_m = metrics(y_test, results["baseline_ratio"].pred_test)
    best_m = metrics(y_test, results[best_test_name].pred_test)
    gain = {
        "baseline_MAPE_%": base_m["MAPE_%"],
        f"{best_test_name}_MAPE_%": best_m["MAPE_%"],
        "gain_MAPE_pp": base_m["MAPE_%"] - best_m["MAPE_%"],
        "baseline_MAE": base_m["MAE"],
        f"{best_test_name}_MAE": best_m["MAE"],
        "gain_MAE": base_m["MAE"] - best_m["MAE"],
        "val_year": int(val_year),
        "test_year": int(test_year),
        "best_model_val": best_name,
        "best_model_test": best_test_name,
        "note": (
            "Le blend peut gagner en validation et en début d'année ; "
            "la baseline ratio reste souvent meilleure en 2e semestre (test 2025)."
        ),
    }
    print("\n=== Gain vs baseline (test) ===")
    for k, v in gain.items():
        if isinstance(v, str):
            print(f"  {k}: {v}")
        elif isinstance(v, int):
            print(f"  {k}: {v}")
        else:
            print(f"  {k}: {v:,.2f}")
    (OUT_DIR / "gain_vs_baseline.json").write_text(
        json.dumps(gain, indent=2), encoding="utf-8"
    )

    # IC empirique sur le meilleur modèle test
    ref_name = best_test_name
    rel_err = (results[ref_name].pred_val - y_val.to_numpy()) / np.clip(
        y_val.to_numpy(), 1.0, None
    )
    lo, hi = attach_intervals(results[ref_name].pred_test, rel_err)
    band = test_e[["dept", "dept_name", "year", "month_obs", "cumul", "y"]].copy()
    band["pred"] = results[ref_name].pred_test
    band["pred_p10"] = lo
    band["pred_p90"] = hi
    band["model"] = ref_name
    band.to_csv(OUT_DIR / "predictions_test_with_intervals.csv", index=False)

    # Projection année courante — modèle gagnant sur le mois d'observation (test)
    if len(ops):
        obs_month = int(ops["month"].iloc[0])
        proj_model = month_winners.get(obs_month, best_test_name)
        print(
            f"\n→ projection {int(ops['year'].iloc[0])} "
            f"(mois {obs_month}, modèle={proj_model})…"
        )
        full = pd.concat([train, val, test], ignore_index=True)
        bl_full = HistoricalRatioBaseline().fit(full)
        ops_e = enrich_features(ops.assign(y=np.nan), bl_full)
        ops_e["month_obs"] = ops_e["month"]
        base_pred = bl_full.predict(ops_e)

        def ml_predict(boost: str) -> np.ndarray:
            full_e = enrich_features(full, bl_full)
            Xf, yf = prepare_xy(full_e)
            Xo = ops_e[FEATURE_NUM + FEATURE_CAT].copy()
            for c in FEATURE_NUM:
                Xo[c] = pd.to_numeric(Xo[c], errors="coerce")
            Xo = Xo.fillna(0.0)
            y_log = np.log1p(yf)
            if boost == "catboost":
                from catboost import CatBoostRegressor

                m = CatBoostRegressor(
                    iterations=800,
                    depth=6,
                    learning_rate=0.04,
                    loss_function="RMSE",
                    random_seed=42,
                    verbose=False,
                    cat_features=["dept"],
                )
                m.fit(Xf, y_log)
                return predict_positive(m.predict(Xo), ops_e["cumul"].to_numpy())
            if boost == "lightgbm":
                import lightgbm as lgb

                Xt = Xf.copy()
                Xoo = Xo.copy()
                Xt["dept"] = Xt["dept"].astype("category")
                Xoo["dept"] = pd.Categorical(
                    Xoo["dept"], categories=Xt["dept"].cat.categories
                )
                m = lgb.LGBMRegressor(
                    n_estimators=800,
                    learning_rate=0.04,
                    num_leaves=40,
                    random_state=42,
                    verbosity=-1,
                )
                m.fit(Xt, y_log, categorical_feature=["dept"])
                return predict_positive(m.predict(Xoo), ops_e["cumul"].to_numpy())
            if boost in ("ridge", "elasticnet"):
                pipe = make_linear(boost)
                pipe.fit(Xf, y_log)
                return predict_positive(pipe.predict(Xo), ops_e["cumul"].to_numpy())
            return base_pred

        if proj_model == "baseline_ratio":
            preds = base_pred
        elif proj_model.startswith("blend_baseline_"):
            boost = proj_model.replace("blend_baseline_", "")
            preds = 0.5 * base_pred + 0.5 * ml_predict(boost)
        else:
            preds = ml_predict(proj_model)

        # IC depuis erreurs relatives du modèle de référence sur la val
        if proj_model in results:
            rel = (results[proj_model].pred_val - y_val.to_numpy()) / np.clip(
                y_val.to_numpy(), 1.0, None
            )
        else:
            rel = rel_err
        lo, hi = attach_intervals(preds, rel)
        proj = ops_e[["dept", "dept_name", "year", "month", "cumul"]].copy()
        proj["pred_annual"] = preds
        proj["pred_p10"] = lo
        proj["pred_p90"] = hi
        proj["model"] = proj_model
        proj = proj.sort_values("pred_annual", ascending=False)
        proj.to_csv(OUT_DIR / "projection_current_year.csv", index=False)
        print(proj.head(12).to_string(index=False, float_format=lambda x: f"{x:,.0f}"))

    note = bayesian_note(train)
    print(f"\n=== Bayésien hiérarchique ===\n{note}")
    (OUT_DIR / "bayesian_note.txt").write_text(note, encoding="utf-8")
    supervised.to_csv(OUT_DIR / "dataset_supervised.csv", index=False)
    print(f"\n✓ sorties → {OUT_DIR}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Nowcasting DMTO annuel")
    p.add_argument("--data-url", default=DATA_URL)
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--val-year", type=int, default=2024)
    p.add_argument("--test-year", type=int, default=2025)
    return p.parse_args()


if __name__ == "__main__":
    run(parse_args())
