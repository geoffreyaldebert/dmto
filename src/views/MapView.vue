<script setup>
import { onMounted } from 'vue'
import FranceMap from '../components/FranceMap.vue'
import SidePanel from '../components/SidePanel.vue'
import { useDmtoData } from '../composables/useDmtoData.js'

const {
  loading,
  error,
  geojson,
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
} = useDmtoData()

onMounted(load)
</script>

<template>
  <div class="layout">
    <SidePanel
      class="panel-col"
      :loading="loading"
      :error="error"
      :department="selectedDept"
      :latest-month="latestMonth"
      :snapshot="latestSnapshot"
      :timeline="timeline"
      :annual-series="annualSeries"
      :reference-month="referenceMonth"
      :forecast="annualForecast"
    />
    <main class="map-col">
      <FranceMap
        :geojson="geojson"
        :totals="mapTotals"
        :selected-code="selectedCode"
        :reference-month="referenceMonth"
        @select="selectDepartment"
      />
    </main>
  </div>
</template>

<style scoped>
.layout {
  display: grid;
  grid-template-columns: minmax(320px, 1fr) 2fr;
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
}

.panel-col {
  min-width: 0;
}

.map-col {
  min-width: 0;
  min-height: 0;
  position: relative;
  background: var(--bg-map);
}

@media (max-width: 900px) {
  .layout {
    grid-template-columns: 1fr;
    grid-template-rows: minmax(50vh, auto) minmax(45vh, 1fr);
    height: auto;
    min-height: 100dvh;
    overflow: visible;
  }

  .panel-col {
    max-height: none;
  }

  .map-col {
    min-height: 55vh;
  }
}
</style>
