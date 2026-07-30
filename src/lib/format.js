const euro = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0,
})

const euroCompact = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  notation: 'compact',
  maximumFractionDigits: 1,
})

const monthLabel = new Intl.DateTimeFormat('fr-FR', {
  month: 'long',
  year: 'numeric',
})

export function formatEuro(value) {
  return euro.format(value ?? 0)
}

export function formatEuroCompact(value) {
  return euroCompact.format(value ?? 0)
}

export function formatMonth(ym) {
  if (!ym) return '—'
  const [y, m] = ym.split('-').map(Number)
  return monthLabel.format(new Date(y, m - 1, 1))
}

export function formatMonthShort(ym) {
  if (!ym) return ''
  const [y, m] = ym.split('-')
  return `${m}/${y.slice(2)}`
}
