<script setup>
import { RouterLink } from 'vue-router'
import { CATEGORIES } from '../lib/dmto.js'
import { formatEuro, formatMonth } from '../lib/format.js'
import DmtoChart from './DmtoChart.vue'
import DmtoAnnualChart from './DmtoAnnualChart.vue'

defineProps({
  loading: Boolean,
  error: { type: String, default: null },
  department: { type: Object, default: null },
  latestMonth: { type: String, default: null },
  snapshot: { type: Object, default: null },
  timeline: { type: Array, default: () => [] },
  annualSeries: { type: Array, default: () => [] },
  referenceMonth: { type: String, default: null },
  forecast: { type: Object, default: null },
})

function categoryMeta(id) {
  return CATEGORIES.find((c) => c.id === id)
}

function modelLabel(name) {
  if (name === 'baseline_ratio') return 'Ratio historique'
  if (name === 'elasticnet') return 'Elastic Net'
  if (name === 'blend_baseline_elasticnet') return 'Blend ratio + Elastic Net'
  if (name === 'sum_categories') return 'Somme des taxes'
  return name || '—'
}

function pct(part, whole) {
  if (!whole) return 0
  return Math.round((part / whole) * 100)
}
</script>

<template>
  <aside class="panel">
    <div class="brand">
      <h1>DMTO</h1>
      <h2>Droits de mutations à titre onéreux par département</h2>
      <p>
        Cliquez sur un département sur la carte pour explorer le détail.
      </p>
    </div>

    <div v-if="loading" class="state">Chargement des recettes...</div>
    <div v-else-if="error" class="state error">{{ error }}</div>

    <template v-else-if="department && snapshot">
      <section class="hero-stat">
        <div class="dept-label">
          <span class="code">{{ department.code }}</span>
          <h2>{{ department.name }}</h2>
        </div>
        <p class="period">Mois le plus récent · {{ formatMonth(latestMonth) }}</p>
        <p class="amount">{{ formatEuro(snapshot.total) }}</p>
        <p class="amount-caption">Recettes du mois</p>
      </section>

      <section v-if="forecast" class="forecast">
        <h3>Anticipation {{ forecast.year }}</h3>
        <p class="forecast-lead">
          Projection du total annuel à partir des cumuls janvier - "mois courant", taxe par
          taxe.
        </p>
        <p class="amount forecast-amount">{{ formatEuro(forecast.total.pred) }}</p>
        <p class="amount-caption">
          Intervalle d'incertitude · {{ formatEuro(forecast.total.predP10) }} –
          {{ formatEuro(forecast.total.predP90) }}
        </p>

        <div v-if="forecast.byCategory?.length" class="cat-forecasts">
          <article
            v-for="row in forecast.byCategory"
            :key="row.id"
            class="cat-forecast"
            :class="{ highlight: row.id === 'TDPF' || row.id === 'TCAD' }"
          >
            <header>
              <span
                class="cat"
                :style="{ '--cat': categoryMeta(row.id)?.color || '#9bb4bd' }"
              >
                {{ row.id }}
              </span>
              <span class="beneficiary">{{ row.beneficiary }}</span>
            </header>
            <p class="cat-label">{{ row.label }}</p>
            <p class="cat-pred">{{ formatEuro(row.pred) }}</p>
            <p class="cat-sub">
              Cumul {{ formatEuro(row.cumul) }} · restant
              {{ formatEuro(Math.max(0, row.pred - row.cumul)) }} ·
              {{ pct(row.cumul, row.pred) }}&nbsp;% encaissé
            </p>
            <p class="cat-sub">
              (modèle : {{ modelLabel(row.model) }})
            </p>
          </article>
        </div>

        <dl class="forecast-meta">
          <div>
            <dt>Cumul toutes taxes</dt>
            <dd>{{ formatEuro(forecast.total.cumul) }}</dd>
          </div>
          <div>
            <dt>Restant estimé</dt>
            <dd>
              {{ formatEuro(Math.max(0, forecast.total.pred - forecast.total.cumul)) }}
            </dd>
          </div>
        </dl>
        <p class="method-link-wrap">
          <RouterLink class="method-link" to="/methode">
            Comment sont calculés ces projections&nbsp;?
          </RouterLink>
        </p>
      </section>

      <section class="table-block">
        <h3>Détail du mois  de {{ formatMonth(latestMonth) }}</h3>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Catégorie</th>
                <th>Libellé</th>
                <th>Nature</th>
                <th class="num">Recettes</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(line, i) in snapshot.lines" :key="i">
                <td>
                  <span
                    class="cat"
                    :style="{
                      '--cat': categoryMeta(line.categorie)?.color || '#9bb4bd',
                    }"
                  >
                    {{ line.categorie }}
                  </span>
                </td>
                <td>{{ line.label }}</td>
                <td>{{ line.nature }}</td>
                <td class="num">{{ formatEuro(line.recettes) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <DmtoChart :timeline="timeline" :department-name="department.name" />
      <DmtoAnnualChart
        :annual-series="annualSeries"
        :forecast="forecast"
        :department-name="department.name"
      />
    </template>

    <details class="about-accordion">
      <summary>Qui est derrière cette réutilisation&nbsp;?</summary>
      <div class="about-body">
        <p>
          Je suis un contributeur open data. Les données sources sont
          <strong>officielles</strong>, publiées par la DGFiP sur
          <a
            href="https://www.data.gouv.fr/datasets/search?q=droits+de+mutation+%C3%A0+titre+on%C3%A9reux&organization=534fff8ea3a7292c64a77f02"
            target="_blank"
            rel="noopener noreferrer"
            >data.gouv.fr</a
          >. Les <strong>projections</strong> présentées ici sont réalisées de
          ma propre initiative&nbsp;: elles n’engagent pas l’administration
          productrice des données.
        </p>
        <p>
          Cette réutilisation vise à faire état des DMTO distribués par
          département, dans un objectif de
          <strong>transparence de la vie publique</strong> - réutilisation de l'open data — et, éventuellement, d’aide aux
          départements pour leur anticipation budgétaire.
        </p>
        <p>
          Code source&nbsp;:
          <a
            href="https://github.com/geoffreyaldebert/dmto"
            target="_blank"
            rel="noopener noreferrer"
            >github.com/geoffreyaldebert/dmto</a
          >.
          Tout composant, code, méthode ou visualisation de ce projet peut être
          <strong>librement réutilisé</strong> sous licence
          <a
            href="https://github.com/geoffreyaldebert/dmto/blob/main/LICENSE"
            target="_blank"
            rel="noopener noreferrer"
            >MIT</a
          >.
        </p>
        <p>
          Si vous détectez une erreur d’interprétation ou une correction à
          apporter, je serai ravi d’en tenir compte. Vous pouvez m’écrire sur
          <a
            href="https://www.linkedin.com/in/geoffrey-aldebert-7a699b17/"
            target="_blank"
            rel="noopener noreferrer"
            >LinkedIn</a
          >.
        </p>
      </div>
    </details>

    <p v-if="referenceMonth && !loading && !error" class="footnote">
      Source des données (hors projections): <a href="https://www.data.gouv.fr/datasets/search?q=droits+de+mutation+%C3%A0+titre+on%C3%A9reux&organization=534fff8ea3a7292c64a77f02">data.gouv.fr</a>
    </p>
  </aside>
</template>

<style scoped>
.panel {
  height: 100%;
  overflow: auto;
  padding: 1.75rem 1.5rem 2rem;
  background:
    linear-gradient(180deg, rgba(18, 56, 69, 0.55), rgba(12, 42, 53, 0.92)),
    var(--bg-panel);
  border-right: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.brand .eyebrow {
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  font-size: 0.68rem;
  color: var(--accent);
  font-weight: 600;
}

.brand h1 {
  margin: 0.35rem 0 0.5rem;
  font-family: var(--font-display);
  font-size: clamp(2.4rem, 4vw, 3.2rem);
  font-weight: 700;
  line-height: 0.95;
  letter-spacing: -0.03em;
}

.lede {
  margin: 0;
  color: var(--ink-muted);
  font-size: 0.92rem;
  line-height: 1.45;
  max-width: 28ch;
}

.method-teaser {
  margin: 0.75rem 0 0;
}

.state {
  padding: 1rem;
  background: var(--accent-soft);
  color: var(--ink);
  border-left: 3px solid var(--accent);
}

.state.error {
  background: rgba(196, 98, 52, 0.15);
  border-left-color: #c46234;
}

.hero-stat {
  padding: 1.1rem 0 0.25rem;
  border-top: 1px solid var(--line);
}

.dept-label {
  display: flex;
  align-items: baseline;
  gap: 0.65rem;
}

.code {
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--bg-deep);
  background: var(--accent);
  padding: 0.15rem 0.4rem;
}

.dept-label h2 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.55rem;
  font-weight: 500;
}

.period {
  margin: 0.65rem 0 0;
  color: var(--ink-faint);
  font-size: 0.8rem;
}

.amount {
  margin: 0.35rem 0 0;
  font-family: var(--font-display);
  font-size: clamp(1.8rem, 3vw, 2.35rem);
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--ink);
}

.amount-caption {
  margin: 0.15rem 0 0;
  color: var(--ink-muted);
  font-size: 0.8rem;
}

.forecast {
  padding: 1rem 0 0.25rem;
  border-top: 1px solid var(--line);
}

.forecast h3 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.05rem;
  font-weight: 500;
}

.forecast-lead {
  margin: 0.35rem 0 0;
  color: var(--ink-muted);
  font-size: 0.8rem;
  line-height: 1.4;
}

.forecast-amount {
  color: var(--accent);
}

.cat-forecasts {
  margin-top: 1rem;
  display: grid;
  gap: 0.65rem;
}

.cat-forecast {
  padding: 0.7rem 0.75rem;
  border: 1px solid var(--line);
  background: rgba(0, 0, 0, 0.14);
}

.cat-forecast.highlight {
  border-color: rgba(232, 165, 75, 0.35);
  background: var(--accent-soft);
}

.cat-forecast header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.beneficiary {
  font-size: 0.68rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--ink-faint);
}

.cat-label {
  margin: 0.35rem 0 0;
  font-size: 0.75rem;
  color: var(--ink-muted);
  line-height: 1.3;
}

.cat-pred {
  margin: 0.25rem 0 0;
  font-family: var(--font-display);
  font-size: 1.15rem;
  font-weight: 600;
  letter-spacing: -0.02em;
}

.cat-sub {
  margin: 0.2rem 0 0;
  font-size: 0.7rem;
  color: var(--ink-faint);
  line-height: 1.35;
}

.forecast-meta {
  margin: 0.85rem 0 0;
  display: grid;
  gap: 0.45rem;
}

.forecast-meta div {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0.75rem;
  font-size: 0.78rem;
  padding: 0.35rem 0;
  border-bottom: 1px solid var(--line);
}

.forecast-meta div:last-child {
  border-bottom: none;
}

.forecast-meta dt {
  margin: 0;
  color: var(--ink-faint);
}

.forecast-meta dd {
  margin: 0;
  font-variant-numeric: tabular-nums;
  text-align: right;
}

.method-link-wrap {
  margin: 0.9rem 0 0;
}

.method-link {
  color: var(--accent);
  font-size: 0.82rem;
  text-decoration: none;
  border-bottom: 1px solid rgba(232, 165, 75, 0.35);
}

.method-link:hover {
  border-bottom-color: var(--accent);
}

.table-block h3 {
  margin: 0 0 0.7rem;
  font-family: var(--font-display);
  font-size: 1.05rem;
  font-weight: 500;
}

.table-wrap {
  overflow: auto;
  border: 1px solid var(--line);
}

table {
  width: 100%;
  min-width: 420px;
  font-size: 0.78rem;
}

th,
td {
  padding: 0.55rem 0.65rem;
  text-align: left;
  border-bottom: 1px solid var(--line);
  vertical-align: top;
}

th {
  color: var(--ink-faint);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-size: 0.65rem;
  background: rgba(0, 0, 0, 0.18);
}

tbody tr:last-child td {
  border-bottom: none;
}

td.num,
th.num {
  text-align: right;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.cat {
  display: inline-block;
  padding: 0.1rem 0.35rem;
  border-left: 3px solid var(--cat);
  background: rgba(255, 255, 255, 0.04);
  font-weight: 600;
  letter-spacing: 0.04em;
  font-size: 0.7rem;
}

.footnote {
  margin-top: 0.25rem;
  padding-top: 0.5rem;
  color: var(--ink-faint);
  font-size: 0.72rem;
  line-height: 1.4;
}

.about-accordion {
  margin-top: auto;
  border-top: 1px solid var(--line);
  padding-top: 0.85rem;
}

.about-accordion summary {
  cursor: pointer;
  list-style: none;
  font-family: var(--font-display);
  font-size: 0.95rem;
  font-weight: 500;
  color: var(--ink);
  padding: 0.15rem 0;
}

.about-accordion summary::-webkit-details-marker {
  display: none;
}

.about-accordion summary::before {
  content: '+';
  display: inline-block;
  width: 1.1rem;
  color: var(--accent);
  font-weight: 600;
}

.about-accordion[open] summary::before {
  content: '−';
}

.about-body {
  margin-top: 0.75rem;
  display: grid;
  gap: 0.7rem;
}

.about-body p {
  margin: 0;
  color: var(--ink-muted);
  font-size: 0.8rem;
  line-height: 1.45;
}

.about-body strong {
  color: var(--ink);
  font-weight: 600;
}

.about-body a {
  color: var(--accent);
}
</style>
