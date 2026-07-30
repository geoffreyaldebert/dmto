<script setup>
import { RouterLink } from 'vue-router'
</script>

<template>
  <div class="method-page">
    <header class="method-header">
      <RouterLink class="back" to="/">← Retour à la carte</RouterLink>
      <p class="eyebrow">Méthode</p>
      <h1>Anticiper le total annuel de DMTO</h1>
      <p class="lede">
        Comment l’application estime, en cours d’année, le montant que chaque
        département aura encaissé au 31 décembre.
      </p>
    </header>

    <article class="method-body">
      <section>
        <h2>Ce que l’on cherche à prédire</h2>
        <p>
          Les données publiées sont des <strong>recouvrements mensuels</strong>
          de la DGFiP, pas directement des ventes immobilières. Il existe en effet un
          décalage administratif entre l’acte et l’encaissement.
        </p>
        <p>
          L’objectif que nous poursuivons sur cette interface n’est pas de prévoir le mois suivant, mais le
          <strong>total annuel</strong> : connaissant le cumul de janvier au
          mois courant, quelle somme sera atteinte fin décembre&nbsp;?
        </p>
      </section>

      <section>
        <h2>Principe du nowcasting</h2>
        <p>
          Chaque estimation correspond à un triplet
          <em>département × année × mois d’observation</em>. La cible est
          toujours le total réellement encaissé sur l’année complète.
        </p>
        <p>
          Exemple&nbsp;: fin juin, on connaît janvier–juin&nbsp;; on projette le
          total de l’année. Le même exercice est possible dès fin janvier jusqu’à
          fin novembre.
        </p>
      </section>

      <section>
        <h2>Projection par taxe</h2>
        <p>
          Les projections sont calculées <strong>séparément par catégorie</strong>
          de DMTO, car les attributaires ne sont pas les mêmes&nbsp;:
        </p>
        <ul>
          <li><strong>TDPF</strong> — taxe départementale de publicité foncière (département).</li>
          <li><strong>TCAD</strong> — taxe communale additionnelle (communes).</li>
          <li><strong>DDE</strong> et <strong>TDAD</strong> — autres droits / taxes départementales.</li>
        </ul>
        <p>
          Le total affiché est la somme de ces projections. Chaque taxe dispose
          de ses propres ratios historiques et de son propre modèle du mois.
        </p>
      </section>

      <section>
        <h2>Modèles comparés</h2>
        <ol>
          <li>
            <strong>Ratio historique (baseline)</strong> — pour chaque
            département et chaque mois, on calcule la part moyenne du total
            annuel déjà encaissée par le passé. La projection devient
            <code>cumul ÷ ratio</code>.
          </li>
          <li>
            <strong>Elastic Net</strong> — régression régularisée sur le
            logarithme du total annuel, avec le département en variable
            catégorielle, le cumul, le rythme récent, le total de l’année
            précédente, un indicateur Covid (2020), etc.
          </li>
          <li>
            <strong>Blend</strong> — moyenne du ratio historique et de
            l’Elastic Net, utile surtout en début d’année quand le cumul est
            encore peu informatif.
          </li>
        </ol>
      </section>

      <section>
        <h2>Quel modèle selon le mois&nbsp;?</h2>
        <p>
          La validation est <strong>chronologique</strong> (pas de tirage
          aléatoire)&nbsp;: entraînement sur le passé, test sur une année
          ultérieure. On retient, pour chaque mois d’observation, le modèle qui
          a le mieux performé (MAPE) sur l’année de test.
        </p>
        <ul>
          <li>Début d’année (janv., fév., avr., mai)&nbsp;: souvent le <em>blend</em>.</li>
          <li>À partir de juin environ&nbsp;: le <em>ratio historique</em> suffit
            en général, et reste plus robuste.</li>
        </ul>
        <p>
          L’app applique automatiquement ce choix au mois le plus récent
          disponible pour le département sélectionné.
        </p>
      </section>

      <section>
        <h2>Intervalle de confiance</h2>
        <p>
          L’intervalle affiché (P10–P90) est empirique&nbsp;: il repose sur la
          distribution des erreurs relatives du modèle retenu, mesurée sur
          l’année de validation. Ce n’est pas un intervalle bayésien formel,
          mais une bande d’incertitude utile pour la lecture métier.
        </p>
      </section>

      <section>
        <h2>Limites</h2>
        <ul>
          <li>
            Les séries sont bruitées par le calendrier de recouvrement DGFiP.
          </li>
          <li>
            L’année 2020 (Covid) est conservée, avec un indicateur dédié, plutôt
            que d’être exclue.
          </li>
          <li>
            Une rupture de marché (taux, volumes) peut dégrader la projection,
            surtout en début d’année.
          </li>
          <li>
            La précision s’améliore mécaniquement à mesure que le cumul annuel
            grossit.
          </li>
        </ul>
      </section>

      <section>
        <h2>Sources</h2>
        <p>
          Recouvrements DMTO&nbsp;:
          <a
            href="https://www.data.gouv.fr/datasets/droits-de-mutations-a-titre-onereux-dimmeubles-par-collectivite-attributaire"
            target="_blank"
            rel="noopener noreferrer"
            >jeu de données data.gouv.fr</a
          >.
        </p>
      </section>
    </article>

    <footer class="method-footer">
      <RouterLink class="back" to="/">← Retour à la carte</RouterLink>
    </footer>
  </div>
</template>

<style scoped>
.method-page {
  min-height: 100dvh;
  padding: 2rem 1.25rem 3rem;
  background:
    radial-gradient(ellipse 70% 50% at 10% 0%, rgba(61, 158, 143, 0.16), transparent 55%),
    radial-gradient(ellipse 60% 40% at 90% 100%, rgba(232, 165, 75, 0.1), transparent 50%),
    linear-gradient(160deg, #05151c 0%, var(--bg-deep) 45%, #0a2430 100%);
}

.method-header,
.method-body,
.method-footer {
  width: min(720px, 100%);
  margin-inline: auto;
}

.back {
  display: inline-block;
  margin-bottom: 1.25rem;
  color: var(--accent);
  text-decoration: none;
  font-size: 0.9rem;
  font-weight: 500;
}

.back:hover {
  text-decoration: underline;
}

.eyebrow {
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  font-size: 0.68rem;
  color: var(--accent);
  font-weight: 600;
}

.method-header h1 {
  margin: 0.4rem 0 0.6rem;
  font-family: var(--font-display);
  font-size: clamp(1.8rem, 4vw, 2.6rem);
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1.05;
}

.lede {
  margin: 0;
  color: var(--ink-muted);
  font-size: 1.05rem;
  line-height: 1.45;
  max-width: 40ch;
}

.method-body {
  margin-top: 2.25rem;
  display: grid;
  gap: 1.75rem;
}

.method-body section {
  padding-top: 1.25rem;
  border-top: 1px solid var(--line);
}

.method-body h2 {
  margin: 0 0 0.65rem;
  font-family: var(--font-display);
  font-size: 1.25rem;
  font-weight: 500;
}

.method-body p,
.method-body li {
  color: var(--ink-muted);
  font-size: 0.95rem;
  line-height: 1.55;
}

.method-body p {
  margin: 0 0 0.75rem;
}

.method-body p:last-child {
  margin-bottom: 0;
}

.method-body ol,
.method-body ul {
  margin: 0 0 0.75rem;
  padding-left: 1.2rem;
}

.method-body li + li {
  margin-top: 0.45rem;
}

.method-body strong {
  color: var(--ink);
  font-weight: 600;
}

.method-body code {
  font-size: 0.85em;
  padding: 0.1rem 0.35rem;
  background: rgba(255, 255, 255, 0.06);
  color: var(--accent);
}

.method-body a {
  color: var(--accent);
}

.method-footer {
  margin-top: 2.5rem;
  padding-top: 1rem;
  border-top: 1px solid var(--line);
}
</style>
