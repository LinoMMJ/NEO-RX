export function partitionFindings(scores = {}, findings = []) {
  const rows = Object.entries(scores || {}).filter(([, score]) => Number.isFinite(score) && score >= 0 && score <= 1)
    .map(([name, score]) => {
      const finding = findings.find((item) => item.etiqueta === name)
      const threshold = finding?.threshold_usado
      const known = Number.isFinite(threshold) && threshold >= 0 && threshold <= 1
      return { name, score, threshold: known ? threshold : null, above: known && score >= threshold }
    }).sort((a, b) => b.score - a.score)
  return { rows, candidates: rows.filter((row) => row.above), other: rows.filter((row) => !row.above) }
}
