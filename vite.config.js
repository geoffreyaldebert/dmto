import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { copyFileSync, existsSync } from 'node:fs'
import { resolve } from 'node:path'

/** Après build : copie index.html → 404.html pour le routing SPA sur GitHub Pages. */
function spaFallback404() {
  return {
    name: 'spa-fallback-404',
    closeBundle() {
      const dist = resolve(process.cwd(), 'dist')
      const index = resolve(dist, 'index.html')
      const notFound = resolve(dist, '404.html')
      if (existsSync(index)) {
        copyFileSync(index, notFound)
      }
    },
  }
}

// https://vite.dev/config/
// base `/dmto/` pour https://<user>.github.io/dmto/
export default defineConfig({
  base: '/',
  plugins: [vue(), spaFallback404()],
  optimizeDeps: {
    include: ['maplibre-gl'],
  },
})
