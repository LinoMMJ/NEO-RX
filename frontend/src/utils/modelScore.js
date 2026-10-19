// Model output is a score, not calibrated diagnostic certainty.
export function formatModelScore(value) {
  const score = Number(value)
  if (value == null || !Number.isFinite(score) || score < 0 || score > 1) return '—'
  if (score >= 0.999) return '≥99.9/100'
  if (score > 0 && score < 0.001) return '<0.1/100'
  return `${(score * 100).toFixed(1)}/100`
}
