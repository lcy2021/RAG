import { Empty, Typography } from 'antd'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type { EvalSummary } from '../api/types'
import { buildChartRows } from '../lib/exportEval'

const PALETTE = ['#1677ff', '#13c2c2', '#722ed1', '#fa8c16', '#eb2f96', '#52c41a']

type Props = {
  summaries: EvalSummary[]
  metricKeys: string[]
  labels: Map<string, string>
}

export function EvalResultsCharts({ summaries, metricKeys, labels }: Props) {
  const { t } = useTranslation()
  const rows = useMemo(
    () => buildChartRows(summaries, metricKeys, labels),
    [summaries, metricKeys, labels],
  )

  if (!rows.length) {
    return <Empty description={t('experiments.noChartData')} />
  }

  return (
    <div style={{ display: 'grid', gap: 24 }}>
      <section>
        <Typography.Text strong>{t('experiments.chartComposite')}</Typography.Text>
        <div style={{ width: '100%', height: 280, marginTop: 8 }}>
          <ResponsiveContainer>
            <BarChart data={rows} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="variant" tick={{ fontSize: 12 }} />
              <YAxis domain={[0, 1]} tick={{ fontSize: 12 }} />
              <Tooltip
                formatter={(value) =>
                  value == null || Number.isNaN(Number(value))
                    ? '—'
                    : Number(value).toFixed(3)
                }
              />
              <Bar
                dataKey="composite"
                name={t('experiments.composite')}
                fill="#1677ff"
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      {metricKeys.length > 0 ? (
        <section>
          <Typography.Text strong>{t('experiments.chartMetrics')}</Typography.Text>
          <div style={{ width: '100%', height: 300, marginTop: 8 }}>
            <ResponsiveContainer>
              <BarChart data={rows} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="variant" tick={{ fontSize: 12 }} />
                <YAxis domain={[0, 1]} tick={{ fontSize: 12 }} />
                <Tooltip
                  formatter={(value) =>
                    value == null || Number.isNaN(Number(value))
                      ? '—'
                      : Number(value).toFixed(3)
                  }
                />
                <Legend />
                {metricKeys.map((metric, index) => (
                  <Bar
                    key={metric}
                    dataKey={metric}
                    name={metric}
                    fill={PALETTE[index % PALETTE.length]}
                    radius={[4, 4, 0, 0]}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      ) : null}

      <section>
        <Typography.Text strong>{t('experiments.chartLatency')}</Typography.Text>
        <div style={{ width: '100%', height: 260, marginTop: 8 }}>
          <ResponsiveContainer>
            <BarChart data={rows} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="variant" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} unit="ms" />
              <Tooltip
                formatter={(value) =>
                  value == null || Number.isNaN(Number(value)) ? '—' : `${Number(value)} ms`
                }
              />
              <Bar
                dataKey="latencyP95"
                name={t('experiments.latencyP95')}
                fill="#fa8c16"
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>
    </div>
  )
}
