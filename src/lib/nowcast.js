/**
 * Nowcasting DMTO annuel — modèles portables par taxe.
 * Artefacts v2 : /nowcast/artifacts.json
 */

function clip(x, lo, hi) {
  return Math.min(hi, Math.max(lo, x))
}

/** Résout un scope (TDPF, TCAD, …) ou retombe sur le TOTAL racine (v1). */
export function resolveScope(artifacts, scopeId = 'TOTAL') {
  if (artifacts?.scopes?.[scopeId]) return artifacts.scopes[scopeId]
  if (scopeId === 'TOTAL' && artifacts?.baseline) return artifacts
  return null
}

function shareFor(scope, dept, month) {
  const key = `${dept}|${month}`
  const s =
    scope.baseline.dept_month_share[key] ??
    scope.baseline.national_share[String(month)] ??
    0.5
  return clip(s, 0.02, 0.98)
}

export function baselinePredict(scope, dept, month, cumul) {
  if (cumul <= 0) return 0
  const share = shareFor(scope, dept, month)
  return cumul / share
}

function oneHotDept(scope, dept) {
  const cats = scope.elasticnet.categories[0] || []
  return cats.map((c) => (c === dept ? 1 : 0))
}

function standardize(scope, numValues) {
  const { num_mean: mean, num_scale: scale } = scope.elasticnet
  return numValues.map((v, i) => {
    const s = scale[i] || 1
    return (v - mean[i]) / (s === 0 ? 1 : s)
  })
}

export function elasticnetPredict(scope, features, cumul) {
  const { feature_num: nums, coef, intercept } = scope.elasticnet
  const rawNum = nums.map((k) => Number(features[k]) || 0)
  const scaled = standardize(scope, rawNum)
  const oh = oneHotDept(scope, String(features.dept))
  const x = scaled.concat(oh)
  let logPred = intercept
  for (let i = 0; i < coef.length; i += 1) {
    logPred += coef[i] * (x[i] || 0)
  }
  const pred = Math.expm1(logPred)
  return Math.max(pred, cumul)
}

export function modelNameForMonth(scope, month) {
  return scope.model_by_month?.[String(month)] || 'baseline_ratio'
}

export function predictAnnual(scope, { dept, month, cumul, features }) {
  const model = modelNameForMonth(scope, month)
  const baseline = baselinePredict(scope, dept, month, cumul)
  let pred = baseline

  if (cumul > 0 && model === 'elasticnet') {
    pred = elasticnetPredict(scope, features, cumul)
  } else if (cumul > 0 && model === 'blend_baseline_elasticnet') {
    const wB = scope.blend?.weight_baseline ?? 0.5
    const wM = scope.blend?.weight_ml ?? 0.5
    const ml = elasticnetPredict(scope, features, cumul)
    pred = wB * baseline + wM * ml
  }

  const band = scope.intervals?.[model] || scope.intervals?.baseline_ratio
  const q10 = band?.rel_q10 ?? -0.05
  const q90 = band?.rel_q90 ?? 0.1

  return {
    model,
    pred,
    predP10: pred * (1 + q10),
    predP90: pred * (1 + q90),
    baseline,
    cumul,
    month,
    year: features.year,
    shareUsed: shareFor(scope, dept, month),
  }
}

function seriesAmount(snap, category) {
  if (!snap) return 0
  if (!category || category === 'TOTAL') return snap.total ?? 0
  return snap.byCat?.[category] ?? 0
}

/**
 * @param {{ months: Map<string, any>, code: string }} dept
 * @param {string} latestYm
 * @param {object} scope artefacts d'un scope
 * @param {string} category TOTAL | TDPF | TCAD | …
 */
export function buildNowcastFeatures(dept, latestYm, scope, category = 'TOTAL') {
  if (!dept || !latestYm || !scope) return null
  const [yearStr, monthStr] = latestYm.split('-')
  const year = Number(yearStr)
  const month = Number(monthStr)
  if (!year || !month || month > 11) return null

  const series = []
  for (let m = 1; m <= month; m += 1) {
    const key = `${year}-${String(m).padStart(2, '0')}`
    series.push({
      month: m,
      amount: seriesAmount(dept.months.get(key), category),
    })
  }

  const cumul = series.reduce((s, r) => s + r.amount, 0)
  const amount = series[series.length - 1]?.amount ?? 0
  const prev = series.length > 1 ? series[series.length - 2].amount : null
  const mom_change = prev == null ? 0 : amount - prev
  const last3 = series.slice(-3).map((r) => r.amount)
  const ma3 = last3.reduce((s, v) => s + v, 0) / last3.length

  let prev_year_total = 0
  for (let m = 1; m <= 12; m += 1) {
    const key = `${year - 1}-${String(m).padStart(2, '0')}`
    prev_year_total += seriesAmount(dept.months.get(key), category)
  }

  const hist_share_global = shareFor(scope, dept.code, month)
  const ratio_vs_prev_year = prev_year_total > 0 ? cumul / prev_year_total : 0
  const pace_vs_hist =
    hist_share_global > 0 && prev_year_total > 0
      ? cumul / (hist_share_global * prev_year_total)
      : 0
  const baseline_pred = cumul > 0 ? cumul / hist_share_global : 0

  const features = {
    dept: dept.code,
    month_obs: month,
    year,
    covid: year === 2020 ? 1 : 0,
    cumul,
    amount,
    mom_change,
    ma3,
    prev_year_total,
    ratio_vs_prev_year,
    hist_share_global,
    pace_vs_hist,
    baseline_pred,
    log_cumul: Math.log1p(Math.max(0, cumul)),
    log_prev_year: Math.log1p(Math.max(0, prev_year_total)),
    log_baseline: Math.log1p(Math.max(0, baseline_pred)),
  }

  return { dept: dept.code, month, cumul, features, year, category }
}

const DEFAULT_ORDER = ['TDPF', 'TCAD', 'DDE', 'TDAD']

/**
 * Projections par taxe + total (somme des taxes projetées).
 */
export function predictAnnualByCategory(artifacts, dept, latestYm) {
  if (!artifacts || !dept || !latestYm) return null

  const order = (artifacts.scope_order || DEFAULT_ORDER).filter((id) => id !== 'TOTAL')
  const byCategory = []

  for (const id of order) {
    const scope = resolveScope(artifacts, id)
    if (!scope) continue
    const ctx = buildNowcastFeatures(dept, latestYm, scope, id)
    if (!ctx) continue
    const pred = predictAnnual(scope, ctx)
    byCategory.push({
      id,
      label: scope.label || id,
      beneficiary: scope.beneficiary || '',
      ...pred,
    })
  }

  if (!byCategory.length) {
    // fallback v1
    const scope = resolveScope(artifacts, 'TOTAL')
    const ctx = buildNowcastFeatures(dept, latestYm, scope, 'TOTAL')
    if (!ctx) return null
    const total = predictAnnual(scope, ctx)
    return { year: total.year, month: total.month, total, byCategory: [] }
  }

  const year = byCategory[0].year
  const month = byCategory[0].month
  const sumPred = byCategory.reduce((s, r) => s + r.pred, 0)
  const sumCumul = byCategory.reduce((s, r) => s + r.cumul, 0)
  const sumP10 = byCategory.reduce((s, r) => s + r.predP10, 0)
  const sumP90 = byCategory.reduce((s, r) => s + r.predP90, 0)

  // Total modèle dédié (optionnel) pour comparaison
  let totalModel = null
  const totalScope = resolveScope(artifacts, 'TOTAL')
  if (totalScope) {
    const ctx = buildNowcastFeatures(dept, latestYm, totalScope, 'TOTAL')
    if (ctx) totalModel = predictAnnual(totalScope, ctx)
  }

  return {
    year,
    month,
    byCategory,
    total: {
      model: 'sum_categories',
      pred: sumPred,
      predP10: sumP10,
      predP90: sumP90,
      cumul: sumCumul,
      month,
      year,
    },
    totalModel,
  }
}
