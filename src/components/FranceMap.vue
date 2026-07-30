<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { colorScale, normalizeDeptCode } from '../lib/dmto.js'
import { formatEuroCompact } from '../lib/format.js'

const props = defineProps({
  geojson: { type: Object, default: null },
  totals: { type: Object, default: () => ({}) },
  selectedCode: { type: String, default: null },
  referenceMonth: { type: String, default: null },
})

const emit = defineEmits(['select'])

const container = ref(null)
let map = null
let popup = null
let hoveredId = null
let interactionsBound = false
let resizeObserver = null

const maxTotal = computed(() =>
  Math.max(0, ...Object.values(props.totals).map(Number)),
)

function enrichGeojson(geojson, totals) {
  const max = Math.max(0, ...Object.values(totals).map(Number))
  return {
    type: 'FeatureCollection',
    features: geojson.features.map((feature) => {
      const rawCode = String(feature.properties.code)
      const code = normalizeDeptCode(rawCode)
      const total = Number(totals[code]) || 0
      return {
        type: 'Feature',
        properties: {
          code: rawCode,
          nom: feature.properties.nom,
          dataCode: code,
          total,
          fill: colorScale(total, max),
        },
        geometry: feature.geometry,
      }
    }),
  }
}

function ensureMap() {
  if (map || !container.value) return

  map = new maplibregl.Map({
    container: container.value,
    style: {
      version: 8,
      sources: {},
      layers: [
        {
          id: 'background',
          type: 'background',
          paint: { 'background-color': '#dce8ec' },
        },
      ],
    },
    center: [2.5, 46.6],
    zoom: 5.2,
    minZoom: 4,
    maxZoom: 9,
    attributionControl: false,
  })

  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
  map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right')

  popup = new maplibregl.Popup({
    closeButton: false,
    closeOnClick: false,
    offset: 10,
    className: 'dept-popup',
  })

  map.on('load', () => {
    syncSource()
  })

  resizeObserver = new ResizeObserver(() => map?.resize())
  resizeObserver.observe(container.value)
}

function syncSource() {
  if (!map || !props.geojson || !map.isStyleLoaded()) return

  const data = enrichGeojson(props.geojson, props.totals)
  const existing = map.getSource('departements')

  if (existing) {
    existing.setData(data)
  } else {
    map.addSource('departements', {
      type: 'geojson',
      data,
      promoteId: 'code',
    })

    map.addLayer({
      id: 'departements-fill',
      type: 'fill',
      source: 'departements',
      paint: {
        'fill-color': ['get', 'fill'],
        'fill-opacity': [
          'case',
          ['boolean', ['feature-state', 'hover'], false],
          0.95,
          0.88,
        ],
      },
    })

    map.addLayer({
      id: 'departements-outline',
      type: 'line',
      source: 'departements',
      paint: {
        'line-color': 'rgba(7, 28, 36, 0.35)',
        'line-width': 0.7,
      },
    })

    bindInteractions()
  }

  updateSelectionStyle()
  map.resize()
}

function updateSelectionStyle() {
  if (!map?.getLayer('departements-outline')) return
  const selected = props.selectedCode ?? ''
  map.setPaintProperty('departements-outline', 'line-color', [
    'case',
    ['==', ['get', 'dataCode'], selected],
    '#071c24',
    'rgba(7, 28, 36, 0.35)',
  ])
  map.setPaintProperty('departements-outline', 'line-width', [
    'case',
    ['==', ['get', 'dataCode'], selected],
    2.4,
    0.7,
  ])
}

function bindInteractions() {
  if (!map || interactionsBound) return
  interactionsBound = true

  map.on('mousemove', 'departements-fill', (e) => {
    map.getCanvas().style.cursor = 'pointer'
    const feature = e.features?.[0]
    if (!feature) return

    const id = feature.id
    if (hoveredId !== null && hoveredId !== id) {
      map.setFeatureState({ source: 'departements', id: hoveredId }, { hover: false })
    }
    hoveredId = id
    map.setFeatureState({ source: 'departements', id }, { hover: true })

    const { nom, total, code } = feature.properties
    popup
      .setLngLat(e.lngLat)
      .setHTML(
        `<strong>${nom}</strong><span>${code}</span><em>${formatEuroCompact(total)}</em>`,
      )
      .addTo(map)
  })

  map.on('mouseleave', 'departements-fill', () => {
    map.getCanvas().style.cursor = ''
    if (hoveredId !== null) {
      map.setFeatureState({ source: 'departements', id: hoveredId }, { hover: false })
      hoveredId = null
    }
    popup?.remove()
  })

  map.on('click', 'departements-fill', (e) => {
    const feature = e.features?.[0]
    if (!feature) return
    emit('select', feature.properties.dataCode || feature.properties.code)
  })
}

onMounted(() => {
  ensureMap()
  syncSource()
})

onUnmounted(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  popup?.remove()
  map?.remove()
  map = null
  interactionsBound = false
})

watch(
  () => [props.geojson, props.totals],
  () => {
    ensureMap()
    if (!map) return
    if (map.isStyleLoaded()) syncSource()
    else map.once('load', syncSource)
  },
)

watch(
  () => props.selectedCode,
  () => updateSelectionStyle(),
)
</script>

<template>
  <div class="map-shell">
    <div ref="container" class="map-canvas" />
    <div class="map-legend" v-if="maxTotal > 0">
      <span>Faible</span>
      <div class="ramp" aria-hidden="true" />
      <span>Élevé</span>
      <p v-if="referenceMonth">Totaux {{ referenceMonth }}</p>
    </div>
  </div>
</template>

<style scoped>
.map-shell {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 420px;
}

.map-canvas {
  width: 100%;
  height: 100%;
}

.map-legend {
  position: absolute;
  left: 1rem;
  bottom: 1rem;
  z-index: 2;
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 0.45rem 0.6rem;
  align-items: center;
  padding: 0.7rem 0.85rem;
  background: rgba(255, 255, 255, 0.88);
  color: #0c2a35;
  font-size: 0.72rem;
  letter-spacing: 0.02em;
  backdrop-filter: blur(8px);
  box-shadow: 0 8px 24px rgba(7, 28, 36, 0.12);
}

.map-legend p {
  grid-column: 1 / -1;
  margin: 0;
  color: #5a7380;
}

.ramp {
  height: 8px;
  min-width: 88px;
  border-radius: 999px;
  background: linear-gradient(
    90deg,
    #b7c9d0 0%,
    #7db0a8 35%,
    #3d9e8f 55%,
    #e8a54b 80%,
    #c46234 100%
  );
}

:deep(.dept-popup) .maplibregl-popup-content {
  padding: 0.55rem 0.7rem;
  background: #071c24;
  color: #e8f2f5;
  border-radius: 0;
  box-shadow: 0 10px 28px rgba(3, 16, 22, 0.35);
  display: grid;
  gap: 0.15rem;
  font-family: var(--font-body);
}

:deep(.dept-popup) .maplibregl-popup-tip {
  border-top-color: #071c24;
}

:deep(.dept-popup) strong {
  font-family: var(--font-display);
  font-size: 0.95rem;
}

:deep(.dept-popup) span {
  color: #9bb4bd;
  font-size: 0.72rem;
}

:deep(.dept-popup) em {
  font-style: normal;
  color: #e8a54b;
  font-weight: 600;
  font-size: 0.85rem;
}

:deep(.maplibregl-ctrl-group) {
  border-radius: 0;
  box-shadow: 0 8px 20px rgba(7, 28, 36, 0.15);
}
</style>
