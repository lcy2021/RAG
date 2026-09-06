import { Empty, Space, Tag, Typography } from 'antd'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type { EvalSummary } from '../api/types'
import { buildChartRows, type ChartRow } from '../lib/exportEval'

const DEFAULT_FILL = '#1677ff'
const WINNER_FILL = '#52c41a'
const LATENCY_FILL = '#fa8c16'
const LABEL_STYLE = { fontSize: 12, fill: 'rgba(247, 248, 248, 0.88)' } as const

type Props = {
  summaries: EvalSummary[]
  metricKeys: string[]
  labels: Map<string, string>
}

function formatScore(value: unknown): string {
  if (value == null || Number.isNaN(Number(value))) {
    return '—'
  }
  return Number(value).toFixed(3)
}

function formatLatency(value: unknown): string {
  if (value == null || Number.isNaN(Number(value))) {
    return '—'
  }
  return `${Math.round(Number(value))}`
}

/** Variant IDs that tie for best value on a numeric chart key. */
function winnerIdsForKey(
  rows: ChartRow[],
  key: string,
  mode: 'max' | 'min',
): Set<string> {
  const values = rows
    .map((row) => ({ id: row.variantId, value: row[key] }))
    .filter(
      (item): item is { id: string; value: number } =>
        typeof item.value === 'number' && !Number.isNaN(item.value),
    )
  if (!values.length) {
    return new Set()
  }
  const best =
    mode === 'max'
      ? Math.max(...values.map((item) => item.value))
      : Math.min(...values.map((item) => item.value))
  return new Set(values.filter((item) => item.value === best).map((item) => item.id))
}

function winnerNames(rows: ChartRow[], ids: Set<string>): string[] {
  return rows.filter((row) => ids.has(row.variantId)).map((row) => row.variant)
}

type MetricBarChartProps = {
  title: string
  dataKey: string
  rows: ChartRow[]
  winnerIds: Set<string>
  winnerLabel: string
  tieLabel: string
  yDomain?: [number, number]
  yUnit?: string
  defaultFill: string
  formatValue: (value: unknown) => string
  formatTooltip?: (value: unknown) => string
  formatLabel?: (value: unknown) => string
}

function MetricBarChart({
  title,
  dataKey,
  rows,
  winnerIds,
  winnerLabel,
  tieLabel,
  yDomain,
  yUnit,
  defaultFill,
  formatValue,
  formatTooltip,
  formatLabel,
}: MetricBarChartProps) {
  const winners = winnerNames(rows, winnerIds)
  const isTie = winners.length > 1
  const resultLabel = isTie ? tieLabel : winnerLabel
  const tip = formatTooltip ?? formatValue
  const topLabel = formatLabel ?? formatValue

  return (
    <section>
      <Space wrap size="middle" style={{ width: '100%' }}>
        <Typography.Text strong>{title}</Typography.Text>
        {winners.length > 0 ? (
          <span>
            <Tag color={isTie ? 'blue' : 'success'}>{resultLabel}</Tag>
            <Typography.Text>{winners.join(', ')}</Typography.Text>
          </span>
        ) : null}
      </Space>
      <div style={{ width: '100%', height: 280, marginTop: 8 }}>
        <ResponsiveContainer>
          <BarChart data={rows} margin={{ top: 28, right: 16, left: 0, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="variant"
              tick={{ fontSize: 12 }}
              tickFormatter={(value, index) => {
                const row = rows[index]
                return row && winnerIds.has(row.variantId) ? `${value} ✓` : String(value)
              }}
            />
            <YAxis domain={yDomain} tick={{ fontSize: 12 }} unit={yUnit} />
            <Tooltip
              formatter={(value) => tip(value)}
              labelFormatter={(label, payload) => {
                const row = payload?.[0]?.payload as { variantId?: string } | undefined
                return row?.variantId && winnerIds.has(row.variantId)
                  ? `${label} (${resultLabel})`
                  : String(label)
              }}
            />
            <Bar dataKey={dataKey} name={title} radius={[4, 4, 0, 0]}>
              {rows.map((row) => (
                <Cell
                  key={row.variantId}
                  fill={winnerIds.has(row.variantId) ? WINNER_FILL : defaultFill}
                />
              ))}
              <LabelList dataKey={dataKey} position="top" formatter={topLabel} style={LABEL_STYLE} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}

export function EvalResultsCharts({ summaries, metricKeys, labels }: Props) {
  const { t } = useTranslation()
  const rows = useMemo(
    () => buildChartRows(summaries, metricKeys, labels),
    [summaries, metricKeys, labels],
  )

  const compositeWinners = useMemo(() => winnerIdsForKey(rows, 'composite', 'max'), [rows])
  const latencyWinners = useMemo(() => winnerIdsForKey(rows, 'latencyP95', 'min'), [rows])
  const costWinners = useMemo(() => winnerIdsForKey(rows, 'costAvg', 'min'), [rows])
  const metricWinners = useMemo(() => {
    const map = new Map<string, Set<string>>()
    for (const metric of metricKeys) {
      map.set(metric, winnerIdsForKey(rows, metric, 'max'))
    }
    return map
  }, [metricKeys, rows])

  if (!rows.length) {
    return <Empty description={t('experiments.noChartData')} />
  }

  const winnerTag = t('experiments.winner')
  const tieTag = t('experiments.tie')

  return (
    <div style={{ display: 'grid', gap: 24 }}>
      <MetricBarChart
        title={t('experiments.chartComposite')}
        dataKey="composite"
        rows={rows}
        winnerIds={compositeWinners}
        winnerLabel={winnerTag}
        tieLabel={tieTag}
        yDomain={[0, 1]}
        defaultFill={DEFAULT_FILL}
        formatValue={formatScore}
      />

      {metricKeys.map((metric) => (
        <MetricBarChart
          key={metric}
          title={t('experiments.chartMetric', { metric })}
          dataKey={metric}
          rows={rows}
          winnerIds={metricWinners.get(metric) ?? new Set()}
          winnerLabel={winnerTag}
          tieLabel={tieTag}
          yDomain={[0, 1]}
          defaultFill={DEFAULT_FILL}
          formatValue={formatScore}
        />
      ))}

      <MetricBarChart
        title={t('experiments.chartLatency')}
        dataKey="latencyP95"
        rows={rows}
        winnerIds={latencyWinners}
        winnerLabel={winnerTag}
        tieLabel={tieTag}
        yUnit="ms"
        defaultFill={LATENCY_FILL}
        formatValue={formatLatency}
        formatTooltip={(value) =>
          value == null || Number.isNaN(Number(value)) ? '—' : `${formatLatency(value)} ms`
        }
        formatLabel={(value) =>
          value == null || Number.isNaN(Number(value)) ? '—' : `${formatLatency(value)}ms`
        }
      />

      <MetricBarChart
        title={t('experiments.chartCost')}
        dataKey="costAvg"
        rows={rows}
        winnerIds={costWinners}
        winnerLabel={winnerTag}
        tieLabel={tieTag}
        yUnit="µ$"
        defaultFill={LATENCY_FILL}
        formatValue={formatLatency}
        formatTooltip={(value) =>
          value == null || Number.isNaN(Number(value)) ? '—' : `${formatLatency(value)} micros`
        }
        formatLabel={(value) =>
          value == null || Number.isNaN(Number(value)) ? '—' : `${formatLatency(value)}`
        }
      />
    </div>
  )
}
