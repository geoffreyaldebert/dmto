<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from 'echarts/components'
import { CATEGORIES, TOTAL_SERIES } from '../lib/dmto.js'
import { formatEuro, formatMonthShort } from '../lib/format.js'

use([CanvasRenderer, LineChart, GridComponent, LegendComponent, TooltipComponent])

const props = defineProps({
  timeline: { type: Array, default: () => [] },
  departmentName: { type: String, default: '' },
})

const seriesDefs = [TOTAL_SERIES, ...CATEGORIES]

const option = computed(() => {
  const dates = props.timeline.map((d) => d.date)
  return {
    color: seriesDefs.map((s) => s.color),
    textStyle: {
      fontFamily: 'IBM Plex Sans, sans-serif',
      color: '#9bb4bd',
    },
    grid: {
      left: 16,
      right: 16,
      top: 48,
      bottom: 28,
      containLabel: true,
    },
    legend: {
      top: 0,
      left: 0,
      icon: 'roundRect',
      itemWidth: 12,
      itemHeight: 4,
      textStyle: { color: '#c5d7dd', fontSize: 11 },
      data: seriesDefs.map((s) => s.short),
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(7, 28, 36, 0.95)',
      borderColor: 'rgba(232, 242, 245, 0.12)',
      textStyle: { color: '#e8f2f5', fontSize: 12 },
      valueFormatter: (v) => formatEuro(v),
    },
    xAxis: {
      type: 'category',
      data: dates.map(formatMonthShort),
      boundaryGap: false,
      axisLine: { lineStyle: { color: 'rgba(232, 242, 245, 0.15)' } },
      axisLabel: { color: '#6d8892', fontSize: 10, hideOverlap: true },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: 'rgba(232, 242, 245, 0.08)' } },
      axisLabel: {
        color: '#6d8892',
        fontSize: 10,
        formatter: (v) =>
          new Intl.NumberFormat('fr-FR', {
            notation: 'compact',
            maximumFractionDigits: 1,
          }).format(v),
      },
    },
    series: seriesDefs.map((s) => ({
      name: s.short,
      type: 'line',
      showSymbol: false,
      smooth: 0.2,
      lineStyle: {
        width: s.id === 'TOTAL' ? 2.5 : 1.5,
        type: s.id === 'TOTAL' ? 'solid' : 'solid',
        opacity: s.id === 'TOTAL' ? 1 : 0.9,
      },
      emphasis: { focus: 'series' },
      data: props.timeline.map((row) =>
        s.id === 'TOTAL' ? row.total : row[s.id] ?? 0,
      ),
    })),
  }
})
</script>

<template>
  <div class="chart-block">
    <header>
      <h3>Évolution mensuelle</h3>
      <p v-if="departmentName">{{ departmentName }} — total et sous-catégories</p>
    </header>
    <VChart class="chart" :option="option" autoresize />
  </div>
</template>

<style scoped>
.chart-block {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-height: 280px;
}

header h3 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.05rem;
  font-weight: 500;
  color: var(--ink);
}

header p {
  margin: 0.2rem 0 0;
  color: var(--ink-muted);
  font-size: 0.8rem;
}

.chart {
  width: 100%;
  height: 260px;
}
</style>
