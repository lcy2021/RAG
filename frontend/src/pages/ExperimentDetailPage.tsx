import { Button, Card, Dropdown, Popconfirm, Progress, Space, Table, Tag, Typography } from 'antd'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'

import {
  useExperiment,
  useExperimentRun,
  useExperimentRuns,
  usePromoteExperimentRun,
  useStartExperimentRun,
} from '../api/hooks'
import type { EvalSummary, EvalVariantProgress } from '../api/types'
import { EvalResultsCharts } from '../components/EvalResultsCharts'
import { FormPageHeader } from '../components/FormPageHeader'
import { useMessage } from '../hooks/useMessage'
import { exportRunJson, exportScoresCsv, exportSummariesCsv } from '../lib/exportEval'

function statusTagColor(status: string): string {
  if (status === 'succeeded') return 'success'
  if (status === 'failed') return 'error'
  if (status === 'running' || status === 'queued') return 'processing'
  return 'default'
}

export function ExperimentDetailPage() {
  const { t } = useTranslation()
  const message = useMessage()
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const experiment = useExperiment(id ?? null)
  const runs = useExperimentRuns(id ?? null)
  const startRun = useStartExperimentRun(id ?? '')
  const promote = usePromoteExperimentRun(id ?? '')
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const activeRunId = selectedRunId ?? runs.data?.[0]?.id ?? null
  const runDetail = useExperimentRun(id ?? null, activeRunId)

  useEffect(() => {
    if (runDetail.data?.status === 'succeeded' || runDetail.data?.status === 'failed') {
      void runs.refetch()
    }
  }, [runDetail.data?.status, runs])

  const variantLabels = useMemo(() => {
    const map = new Map<string, string>()
    for (const item of runDetail.data?.variants ?? []) {
      map.set(item.id, item.label)
    }
    if (map.size === 0) {
      const snapshot = runDetail.data?.snapshot as
        | { variants?: Array<{ id: string; label: string }> }
        | undefined
      for (const item of snapshot?.variants ?? []) {
        map.set(item.id, item.label)
      }
    }
    return map
  }, [runDetail.data])

  if (experiment.isLoading) {
    return (
      <>
        <FormPageHeader title={t('experiments.title')} backTo="/experiments" />
        <Typography.Text type="secondary">{t('common.loading')}</Typography.Text>
      </>
    )
  }

  if (!experiment.data) {
    return (
      <>
        <FormPageHeader title={t('experiments.title')} backTo="/experiments" />
        <Typography.Text type="secondary">{t('experiments.notFound')}</Typography.Text>
        <Button type="link" onClick={() => navigate('/experiments')}>
          {t('common.back')}
        </Button>
      </>
    )
  }

  const detail = experiment.data
  const metricKeys = Array.from(
    new Set((runDetail.data?.summaries ?? []).flatMap((row) => Object.keys(row.metrics || {}))),
  )
  const canPromote =
    runDetail.data?.status === 'succeeded' && Boolean(runDetail.data.winner_variant_id)
  const hasResults =
    runDetail.data?.status === 'succeeded' && (runDetail.data.summaries?.length ?? 0) > 0
  const hasActiveProgress = (runDetail.data?.variants ?? []).some(
    (item) => item.status === 'running' || item.done_items > 0,
  )
  const runBusy =
    runDetail.data?.status === 'running' ||
    (runDetail.data?.status === 'queued' && hasActiveProgress) ||
    startRun.isPending
  const pipelineProgress = runDetail.data?.variants ?? []

  return (
    <>
      <FormPageHeader title={detail.name} backTo="/experiments" />
      <Card style={{ marginBottom: 16 }}>
        <Space wrap size="large">
          <Typography.Text>
            {t('experiments.scenario')}:{' '}
            <Link to={`/scenarios/${detail.scenario_id}`}>
              {detail.scenario_name || detail.scenario_id.slice(0, 8)}
            </Link>
          </Typography.Text>
          <Typography.Text>
            {t('experiments.metrics')}: {detail.metric_plugins.join(', ')}
          </Typography.Text>
        </Space>
        <div style={{ marginTop: 16 }}>
          <Space wrap>
            <Button
              type="primary"
              loading={startRun.isPending}
              disabled={runBusy && !startRun.isPending}
              onClick={async () => {
                try {
                  const run = await startRun.mutateAsync()
                  setSelectedRunId(run.id)
                  message.success(t('experiments.runQueued'))
                } catch (error) {
                  message.error(error instanceof Error ? error.message : t('experiments.runFailed'))
                }
              }}
            >
              {t('experiments.runNow')}
            </Button>
            <Popconfirm
              title={t('experiments.promoteConfirm')}
              disabled={!canPromote || promote.isPending}
              onConfirm={async () => {
                if (!runDetail.data) return
                try {
                  const result = await promote.mutateAsync({ runId: runDetail.data.id })
                  message.success(
                    t('experiments.promoted', {
                      pipeline: result.query_pipeline_name || result.query_pipeline_id,
                    }),
                  )
                } catch (error) {
                  message.error(
                    error instanceof Error ? error.message : t('experiments.promoteFailed'),
                  )
                }
              }}
            >
              <Button disabled={!canPromote} loading={promote.isPending}>
                {t('experiments.promoteWinner')}
              </Button>
            </Popconfirm>
            <Dropdown
              disabled={!hasResults || !runDetail.data}
              menu={{
                items: [
                  {
                    key: 'summaries',
                    label: t('experiments.exportSummariesCsv'),
                    onClick: () => {
                      if (!runDetail.data) return
                      exportSummariesCsv(runDetail.data, variantLabels, detail.name)
                      message.success(t('experiments.exportDone'))
                    },
                  },
                  {
                    key: 'scores',
                    label: t('experiments.exportScoresCsv'),
                    onClick: () => {
                      if (!runDetail.data) return
                      exportScoresCsv(runDetail.data, variantLabels, detail.name)
                      message.success(t('experiments.exportDone'))
                    },
                  },
                  {
                    key: 'json',
                    label: t('experiments.exportJson'),
                    onClick: () => {
                      if (!runDetail.data) return
                      exportRunJson(runDetail.data, variantLabels, detail.name)
                      message.success(t('experiments.exportDone'))
                    },
                  },
                ],
              }}
            >
              <Button disabled={!hasResults}>{t('experiments.export')}</Button>
            </Dropdown>
          </Space>
          <Typography.Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 0 }}>
            {t('experiments.runHint')}
          </Typography.Paragraph>
          <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
            {t('experiments.promoteHint')}
          </Typography.Paragraph>
        </div>
      </Card>

      <Card title={t('experiments.runsTitle')} style={{ marginBottom: 16 }}>
        <Table
          rowKey="id"
          size="small"
          loading={runs.isLoading}
          dataSource={runs.data}
          pagination={false}
          onRow={(row) => ({
            onClick: () => setSelectedRunId(row.id),
            style: {
              cursor: 'pointer',
              background: row.id === activeRunId ? 'rgba(22, 119, 255, 0.06)' : undefined,
            },
          })}
          columns={[
            {
              title: t('common.status'),
              dataIndex: 'status',
              width: 120,
              render: (status: string) => (
                <Tag color={statusTagColor(status)}>{status}</Tag>
              ),
            },
            {
              title: t('experiments.createdAt'),
              dataIndex: 'created_at',
              render: (value: string) => new Date(value).toLocaleString(),
            },
            {
              title: t('experiments.error'),
              dataIndex: 'error_message',
              ellipsis: true,
              render: (value: string | null) => value || t('common.none'),
            },
          ]}
        />
      </Card>

      <Card title={t('experiments.resultsTitle')} style={{ marginBottom: 16 }}>
        {runDetail.isLoading ? (
          <Typography.Text type="secondary">{t('common.loading')}</Typography.Text>
        ) : !runDetail.data ? (
          <Typography.Text type="secondary">{t('experiments.noRuns')}</Typography.Text>
        ) : runDetail.data.status === 'queued' || runDetail.data.status === 'running' ? (
          <>
            <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
              {t('experiments.runInProgress', { status: runDetail.data.status })}
            </Typography.Paragraph>
            <Table
              rowKey="id"
              size="small"
              pagination={false}
              dataSource={pipelineProgress}
              columns={[
                {
                  title: t('experiments.variant'),
                  render: (_: unknown, row: EvalVariantProgress) =>
                    row.query_pipeline_name || row.label,
                },
                {
                  title: t('common.status'),
                  dataIndex: 'status',
                  width: 120,
                  render: (status: string) => (
                    <Tag color={statusTagColor(status)}>{status}</Tag>
                  ),
                },
                {
                  title: t('experiments.itemProgress'),
                  width: 220,
                  render: (_: unknown, row: EvalVariantProgress) => {
                    const total = row.total_items || 0
                    const percent = total > 0 ? Math.round((row.done_items / total) * 100) : 0
                    return (
                      <Progress
                        percent={percent}
                        size="small"
                        status={
                          row.status === 'failed'
                            ? 'exception'
                            : row.status === 'succeeded'
                              ? 'success'
                              : 'active'
                        }
                        format={() => `${row.done_items}/${total}`}
                      />
                    )
                  },
                },
                {
                  title: t('experiments.error'),
                  dataIndex: 'error_message',
                  ellipsis: true,
                  render: (value: string | null) => value || t('common.none'),
                },
              ]}
            />
          </>
        ) : (
          <Table
            rowKey="id"
            size="small"
            dataSource={runDetail.data.summaries}
            pagination={false}
            columns={[
              {
                title: t('experiments.rank'),
                dataIndex: 'rank',
                width: 70,
              },
              {
                title: t('experiments.variant'),
                render: (_, row: EvalSummary) => (
                  <Space>
                    <span>
                      {variantLabels.get(row.compare_variant_id) ??
                        row.compare_variant_id.slice(0, 8)}
                    </span>
                    {row.is_winner ? <Tag color="success">{t('experiments.winner')}</Tag> : null}
                  </Space>
                ),
              },
              {
                title: t('experiments.composite'),
                dataIndex: 'composite_score',
                render: (value: number | null) =>
                  value == null ? t('common.none') : value.toFixed(3),
              },
              ...metricKeys.map((metric) => ({
                title: metric,
                render: (_: unknown, row: EvalSummary) => {
                  const value = row.metrics?.[metric]
                  return value == null ? t('common.none') : Number(value).toFixed(3)
                },
              })),
              {
                title: t('experiments.latencyP95'),
                dataIndex: 'latency_p95_ms',
                render: (value: number | null) => (value == null ? t('common.none') : `${value}ms`),
              },
            ]}
          />
        )}
      </Card>

      {hasResults && runDetail.data ? (
        <Card title={t('experiments.chartsTitle')}>
          <EvalResultsCharts
            summaries={runDetail.data.summaries}
            metricKeys={metricKeys}
            labels={variantLabels}
          />
        </Card>
      ) : null}
    </>
  )
}
