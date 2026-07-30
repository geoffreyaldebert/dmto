import { computed, ref, shallowRef } from 'vue'
import {
  DATA_URL,
  GEOJSON_URL,
  buildDepartmentIndex,
  choroplethTotals,
  departmentAnnualSeries,
  departmentTimeline,
  latestGlobalMonth,
  normalizeDeptCode,
  publicUrl,
} from '../lib/dmto.js'
import { predictAnnualByCategory } from '../lib/nowcast.js'

const ARTIFACTS_URL = publicUrl('nowcast/artifacts.json')

const loading = ref(true)
const error = ref(null)
const index = shallowRef(new Map())
const geojson = shallowRef(null)
const nowcastArtifacts = shallowRef(null)
const selectedCode = ref(null)
const referenceMonth = ref(null)

export function useDmtoData() {
  const selectedDept = computed(() =>
    selectedCode.value ? index.value.get(selectedCode.value) ?? null : null,
  )

  const latestMonth = computed(() => {
    if (!selectedDept.value) return referenceMonth.value
    const dates = [...selectedDept.value.months.keys()].sort()
    return dates.at(-1) ?? referenceMonth.value
  })

  const latestSnapshot = computed(() => {
    if (!selectedDept.value || !latestMonth.value) return null
    return selectedDept.value.months.get(latestMonth.value) ?? null
  })

  const timeline = computed(() => departmentTimeline(selectedDept.value))

  const annualSeries = computed(() =>
    departmentAnnualSeries(selectedDept.value, latestMonth.value),
  )

  const mapTotals = computed(() => {
    if (!referenceMonth.value) return {}
    return choroplethTotals(index.value, referenceMonth.value)
  })

  /** Projection annuelle détaillée par taxe (TDPF / TCAD / …). */
  const annualForecast = computed(() => {
    if (!selectedDept.value || !latestMonth.value || !nowcastArtifacts.value) {
      return null
    }
    return predictAnnualByCategory(
      nowcastArtifacts.value,
      selectedDept.value,
      latestMonth.value,
    )
  })

  async function load() {
    loading.value = true
    error.value = null
    try {
      const [dataRes, geoRes, artRes] = await Promise.all([
        fetch(DATA_URL),
        fetch(GEOJSON_URL),
        fetch(ARTIFACTS_URL),
      ])
      if (!dataRes.ok) throw new Error(`Données DMTO indisponibles (${dataRes.status})`)
      if (!geoRes.ok) throw new Error(`GeoJSON départements indisponible (${geoRes.status})`)
      if (!artRes.ok) {
        throw new Error(
          `Artefacts nowcast introuvables (${artRes.status}). Lancez : npm run nowcast:export`,
        )
      }

      const [rows, geo, artifacts] = await Promise.all([
        dataRes.json(),
        geoRes.json(),
        artRes.json(),
      ])
      const built = buildDepartmentIndex(rows)
      index.value = built
      geojson.value = geo
      nowcastArtifacts.value = artifacts
      referenceMonth.value = latestGlobalMonth(built)

      if (!selectedCode.value) {
        selectedCode.value = built.has('75') ? '75' : [...built.keys()].sort()[0]
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur de chargement'
    } finally {
      loading.value = false
    }
  }

  function selectDepartment(code) {
    const normalized = normalizeDeptCode(code)
    if (index.value.has(normalized)) {
      selectedCode.value = normalized
    }
  }

  return {
    loading,
    error,
    index,
    geojson,
    nowcastArtifacts,
    selectedCode,
    selectedDept,
    referenceMonth,
    latestMonth,
    latestSnapshot,
    timeline,
    annualSeries,
    mapTotals,
    annualForecast,
    load,
    selectDepartment,
  }
}
