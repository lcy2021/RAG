import type { EvalRunDetail, EvalScore, EvalSummary } from '../api/types'

/** UTF-8 BOM so Excel on Windows opens Chinese CSV correctly. */
const UTF8_BOM = '\uFEFF'

function downloadBlob(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

function csvEscape(value: unknown): string {
  const text = value == null ? '' : String(value)
  if (/[",\n\r]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`
  }
  return text
}

function variantLabel(
  variantId: string,
  labels: Map<string, string>,
): string {
  return labels.get(variantId) ?? variantId.slice(0, 8)
}

export function exportSummariesCsv(
  run: EvalRunDetail,
  labels: Map<string, string>,
  experimentName: string,
): void {
  const metricKeys = Array.from(
    new Set(run.summaries.flatMap((row) => Object.keys(row.metrics || {}))),
  )
  const header = [
    'rank',
    'variant',
    'variant_id',
    'is_winner',
    'composite_score',
    ...metricKeys,
    'latency_p50_ms',
    'latency_p95_ms',
  ]
  const lines = [header.join(',')]
  const rows = [...run.summaries].sort((a, b) => (a.rank ?? 999) - (b.rank ?? 999))
  for (const row of rows) {
    lines.push(
      [
        row.rank,
        variantLabel(row.compare_variant_id, labels),
        row.compare_variant_id,
        row.is_winner,
        row.composite_score,
        ...metricKeys.map((metric) => row.metrics?.[metric] ?? ''),
        row.latency_p50_ms,
        row.latency_p95_ms,
      ]
        .map(csvEscape)
        .join(','),
    )
  }
  downloadBlob(
    `${safeName(experimentName)}-summaries-${run.id.slice(0, 8)}.csv`,
    `${UTF8_BOM}${lines.join('\n')}\n`,
    'text/csv;charset=utf-8',
  )
}

export function exportScoresCsv(
  run: EvalRunDetail,
  labels: Map<string, string>,
  experimentName: string,
): void {
  const header = [
    'eval_item_id',
    'variant',
    'variant_id',
    'metric',
    'value',
    'rag_run_id',
  ]
  const lines = [header.join(',')]
  for (const row of run.scores) {
    lines.push(
      [
        row.eval_item_id,
        variantLabel(row.compare_variant_id, labels),
        row.compare_variant_id,
        row.metric,
        row.value,
        row.rag_run_id,
      ]
        .map(csvEscape)
        .join(','),
    )
  }
  downloadBlob(
    `${safeName(experimentName)}-scores-${run.id.slice(0, 8)}.csv`,
    `${UTF8_BOM}${lines.join('\n')}\n`,
    'text/csv;charset=utf-8',
  )
}

export function exportRunJson(
  run: EvalRunDetail,
  labels: Map<string, string>,
  experimentName: string,
): void {
  const payload = {
    experiment_name: experimentName,
    run,
    variant_labels: Object.fromEntries(labels),
  }
  downloadBlob(
    `${safeName(experimentName)}-run-${run.id.slice(0, 8)}.json`,
    `${JSON.stringify(payload, null, 2)}\n`,
    'application/json;charset=utf-8',
  )
}

function safeName(name: string): string {
  return name.trim().replace(/[^\w.-]+/g, '_').slice(0, 48) || 'experiment'
}

export type ChartRow = {
  variant: string
  variantId: string
  composite: number | null
  latencyP95: number | null
  isWinner: boolean
  [metric: string]: string | number | boolean | null
}

export function buildChartRows(
  summaries: EvalSummary[],
  metricKeys: string[],
  labels: Map<string, string>,
): ChartRow[] {
  return [...summaries]
    .sort((a, b) => (a.rank ?? 999) - (b.rank ?? 999))
    .map((row) => {
      const entry: ChartRow = {
        variant: variantLabel(row.compare_variant_id, labels),
        variantId: row.compare_variant_id,
        composite: row.composite_score,
        latencyP95: row.latency_p95_ms,
        isWinner: row.is_winner,
      }
      for (const metric of metricKeys) {
        const value = row.metrics?.[metric]
        entry[metric] = value == null ? null : Number(value)
      }
      return entry
    })
}

export function metricSeriesFromScores(
  scores: EvalScore[],
  labels: Map<string, string>,
): Array<{ metric: string; variant: string; value: number }> {
  const buckets = new Map<string, { sum: number; count: number; variant: string; metric: string }>()
  for (const score of scores) {
    const key = `${score.compare_variant_id}::${score.metric}`
    const current = buckets.get(key) ?? {
      sum: 0,
      count: 0,
      variant: variantLabel(score.compare_variant_id, labels),
      metric: score.metric,
    }
    current.sum += score.value
    current.count += 1
    buckets.set(key, current)
  }
  return Array.from(buckets.values()).map((item) => ({
    metric: item.metric,
    variant: item.variant,
    value: item.count ? item.sum / item.count : 0,
  }))
}
