export const DATA_URL =
  'https://www.data.gouv.fr/api/1/datasets/r/9a8bd034-fdbe-4056-9503-8a3afb03ada4'

/** Préfixe les assets `public/` avec le base Vite (ex. `/dmto/` sur GitHub Pages). */
export function publicUrl(path) {
  const base = import.meta.env.BASE_URL || '/'
  const normalized = String(path).replace(/^\//, '')
  return `${base}${normalized}`
}

export const GEOJSON_URL = publicUrl('departements.geojson')

/** Sous-catégories départementales (TRAD = régional, hors courbes). */
export const CATEGORIES = [
  {
    id: 'DDE',
    short: 'DDE',
    label: "Droits départementaux d'enregistrement",
    color: '#3d9e8f',
  },
  {
    id: 'TCAD',
    short: 'TCAD',
    label: 'Taxe communale additionnelle',
    color: '#5b8def',
  },
  {
    id: 'TDAD',
    short: 'TDAD',
    label: 'Taxe départementale additionnelle',
    color: '#c97b4a',
  },
  {
    id: 'TDPF',
    short: 'TDPF',
    label: 'Taxe départementale de publicité foncière',
    color: '#e8a54b',
  },
]

export const TOTAL_SERIES = {
  id: 'TOTAL',
  short: 'Total',
  label: 'Total DMTO',
  color: '#e8f2f5',
}

/** Corse geojson 2A/2B → code données « 20 ». */
export function normalizeDeptCode(code) {
  if (!code) return code
  const c = String(code)
  if (c === '2A' || c === '2B') return '20'
  return c.padStart(2, '0')
}

export function isDepartmentRow(row) {
  const code = row.collectivite_attributaire
  return code !== 'Non_connus' && !String(code).startsWith('R')
}

/**
 * Indexe les lignes utiles : Map<code, Map<date, { total, lines[], byCat }>>
 */
export function buildDepartmentIndex(rows) {
  const index = new Map()

  for (const row of rows) {
    if (!isDepartmentRow(row)) continue

    const code = normalizeDeptCode(row.collectivite_attributaire)
    if (!index.has(code)) {
      index.set(code, {
        code,
        name: row.libelle_coll_attrib,
        months: new Map(),
      })
    }

    const dept = index.get(code)
    if (row.libelle_coll_attrib && row.libelle_coll_attrib !== 'Non_connus') {
      dept.name = row.libelle_coll_attrib
    }

    if (!dept.months.has(row.date)) {
      dept.months.set(row.date, {
        date: row.date,
        total: 0,
        lines: [],
        byCat: Object.fromEntries(CATEGORIES.map((c) => [c.id, 0])),
      })
    }

    const month = dept.months.get(row.date)
    const amount = Number(row.recettes) || 0
    month.total += amount
    month.lines.push({
      categorie: row.categorie_dmto,
      label: row.label_taxe,
      nature: row.nature_attributaire,
      recettes: amount,
    })
    if (month.byCat[row.categorie_dmto] !== undefined) {
      month.byCat[row.categorie_dmto] += amount
    }
  }

  for (const dept of index.values()) {
    for (const month of dept.months.values()) {
      month.lines.sort((a, b) => b.recettes - a.recettes)
    }
  }

  return index
}

export function latestGlobalMonth(index) {
  let latest = null
  for (const dept of index.values()) {
    for (const date of dept.months.keys()) {
      if (!latest || date > latest) latest = date
    }
  }
  return latest
}

/** Totaux du mois le plus récent par département (pour la chloropleth). */
export function choroplethTotals(index, month) {
  const totals = {}
  for (const [code, dept] of index) {
    const m = dept.months.get(month)
    totals[code] = m ? m.total : 0
  }
  return totals
}

export function departmentTimeline(dept) {
  if (!dept) return []
  return [...dept.months.keys()]
    .sort()
    .map((date) => {
      const m = dept.months.get(date)
      return {
        date,
        total: m.total,
        ...m.byCat,
      }
    })
}

/** Totaux annuels (années closes) + cumul YTD de l'année en cours. */
export function departmentAnnualSeries(dept, currentYm = null) {
  if (!dept) return []

  const byYear = new Map()
  for (const [ym, snap] of dept.months) {
    const year = Number(ym.slice(0, 4))
    const month = Number(ym.slice(5, 7))
    if (!byYear.has(year)) {
      byYear.set(year, { year, total: 0, months: new Set(), byCat: {} })
    }
    const row = byYear.get(year)
    row.total += snap.total || 0
    row.months.add(month)
    for (const [cat, val] of Object.entries(snap.byCat || {})) {
      row.byCat[cat] = (row.byCat[cat] || 0) + (val || 0)
    }
  }

  let currentYear = null
  if (currentYm) currentYear = Number(currentYm.slice(0, 4))

  return [...byYear.values()]
    .sort((a, b) => a.year - b.year)
    .map((row) => {
      const isCurrent = currentYear != null && row.year === currentYear
      const complete = row.months.size >= 12
      return {
        year: row.year,
        total: row.total,
        complete,
        isCurrent,
        byCat: row.byCat,
      }
    })
}

export function colorScale(value, max) {
  if (!max || value <= 0) return '#b7c9d0'
  const t = Math.min(1, Math.sqrt(value / max))
  const stops = [
    [183, 201, 208],
    [125, 176, 168],
    [61, 158, 143],
    [232, 165, 75],
    [196, 98, 52],
  ]
  const scaled = t * (stops.length - 1)
  const i = Math.min(stops.length - 2, Math.floor(scaled))
  const f = scaled - i
  const a = stops[i]
  const b = stops[i + 1]
  const rgb = a.map((c, idx) => Math.round(c + (b[idx] - c) * f))
  return `rgb(${rgb.join(',')})`
}
