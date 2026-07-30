<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from 'echarts/components'
import { formatEuro } from '../lib/format.js'

use([CanvasRenderer, BarChart, GridComponent, LegendComponent, TooltipComponent])

const props = defineProps({
  annualSeries: { type: Array, default: () => [] },
  forecast: { type: Object, default: null },
  departmentName: { type: String, default: '' },
})

const chartRows = computed(() => {
  const collected = props.forecast?.total?.cumul ?? 0
  const projectedTotal = props.forecast?.total?.pred ?? 0
  const remaining = Math.max(0, projectedTotal - collected)

  return props.annualSeries.map((row) => {
    if (row.isCurrent && props.forecast) {
      return {
        year: row.year,
        collected,
        projected: remaining,
        total: projectedTotal,
        isCurrent: true,
      }
    }
    if (row.isCurrent) {
      return {
        year: row.year,
        collected: row.total,
        projected: 0,
        total: row.total,
        isCurrent: true,
      }
    }
    return {
      year: row.year,
      collected: row.total,
      projected: 0,
      total: row.total,
      isCurrent: false,
    }
  })
})

const option = computed(() => {
  const years = chartRows.value.map((r) => String(r.year))
  return {
    color: ['#3d9e8f', '#e8a54b'],
    textStyle: {
      fontFamily: 'IBM Plex Sans, sans-serif',
      color: '#9bb4bd',
    },
    grid: {
      left: 16,
      right: 16,
      top: 44,
      bottom: 24,
      containLabel: true,
    },
    legend: {
      top: 0,
      left: 0,
      icon: 'roundRect',
      itemWidth: 12,
      itemHeight: 8,
      textStyle: { color: '#c5d7dd', fontSize: 11 },
      data: ['Encaissé', 'Projeté'],
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(7, 28, 36, 0.95)',
      borderColor: 'rgba(232, 242, 245, 0.12)',
      textStyle: { color: '#e8f2f5', fontSize: 12 },
      formatter(params) {
        if (!params?.length) return ''
        const year = params[0].axisValue
        const row = chartRows.value.find((r) => String(r.year) === year)
        const lines = [`<strong>${year}</strong>`]
        for (const p of params) {
          if (!p.value) continue
          lines.push(`${p.marker}${p.seriesName} : ${formatEuro(p.value)}`)
        }
        if (row?.isCurrent && row.total) {
          lines.push(`Total anticipé : ${formatEuro(row.total)}`)
        } else if (row?.total) {
          lines.push(`Total annuel : ${formatEuro(row.total)}`)
        }
        return lines.join('<br/>')
      },
    },
    xAxis: {
      type: 'category',
      data: years,
      axisLine: { lineStyle: { color: 'rgba(232, 242, 245, 0.15)' } },
      axisLabel: { color: '#6d8892', fontSize: 11 },
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
    series: [
      {
        name: 'Encaissé',
        type: 'bar',
        stack: 'annual',
        barMaxWidth: 36,
        itemStyle: {
          color: '#3d9e8f',
          borderRadius: [0, 0, 0, 0],
        },
        emphasis: { focus: 'series' },
        data: chartRows.value.map((r) => r.collected),
      },
      {
        name: 'Projeté',
        type: 'bar',
        stack: 'annual',
        barMaxWidth: 36,
        itemStyle: {
          color: 'rgba(232, 165, 75, 0.88)',
          borderRadius: [2, 2, 0, 0],
        },
        emphasis: { focus: 'series' },
        data: chartRows.value.map((r) => (r.projected > 0 ? r.projected : null)),
      },
    ],
  }
})
</script>

<template>
  <div class="chart-block">
    <header>
      <h3>Évolution annuelle</h3>
      <p v-if="departmentName">
        {{ departmentName }} — totaux clos, année en cours empilée
        (encaissé + projeté)
      </p>
    </header>
    <VChart class="chart" :option="option" autoresize />
  </div>
</template>

<style scoped>
.chart-block {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-height: 260px;
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
  height: 240px;
}
</style>
