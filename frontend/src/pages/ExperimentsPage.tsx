import { Button, Popconfirm, Space, Table, Tag, Typography } from 'antd'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'

import { useDeleteExperiment, useExperiments } from '../api/hooks'
import { ListPageHeader } from '../components/ListPageHeader'
import { useMessage } from '../hooks/useMessage'
import { matchesQuery } from '../lib/matchesQuery'

export function ExperimentsPage() {
  const { t } = useTranslation()
  const message = useMessage()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const experiments = useExperiments()
  const remove = useDeleteExperiment()
  const rows = useMemo(
    () =>
      (experiments.data ?? []).filter((row) =>
        matchesQuery(
          [row.name, row.scenario_name, row.compare_spec_name, ...row.metric_plugins],
          query,
        ),
      ),
    [experiments.data, query],
  )

  return (
    <>
      <ListPageHeader
        title={t('experiments.title')}
        subtitle={t('experiments.subtitle')}
        query={query}
        onQueryChange={setQuery}
        onAdd={() => navigate('/experiments/new')}
      />
      <Table
        style={{ marginTop: 16 }}
        rowKey="id"
        size="small"
        loading={experiments.isLoading}
        dataSource={rows}
        pagination={false}
        columns={[
          {
            title: t('common.name'),
            dataIndex: 'name',
            render: (name: string, row) => <Link to={`/experiments/${row.id}`}>{name}</Link>,
          },
          {
            title: t('experiments.scenario'),
            dataIndex: 'scenario_name',
            render: (value: string | null) => value || t('common.none'),
          },
          {
            title: t('experiments.metrics'),
            render: (_, row) =>
              row.metric_plugins.length > 0 ? (
                <Space size={[4, 4]} wrap>
                  {row.metric_plugins.map((metric) => (
                    <Tag key={metric} style={{ marginInlineEnd: 0 }}>
                      {metric}
                    </Tag>
                  ))}
                </Space>
              ) : (
                t('common.none')
              ),
          },
          {
            title: t('experiments.runCount'),
            dataIndex: 'run_count',
            width: 100,
          },
          {
            title: '',
            width: 80,
            render: (_, row) => (
              <Popconfirm
                title={t('experiments.deleteConfirm')}
                onConfirm={async () => {
                  try {
                    await remove.mutateAsync(row.id)
                    message.success(t('common.deleted'))
                  } catch (error) {
                    message.error(
                      error instanceof Error ? error.message : t('common.deleteFailed'),
                    )
                  }
                }}
              >
                <Button danger type="link" size="small">
                  {t('common.delete')}
                </Button>
              </Popconfirm>
            ),
          },
        ]}
      />
      {!experiments.isLoading && rows.length === 0 ? (
        <Typography.Paragraph type="secondary" style={{ marginTop: 12 }}>
          {t('experiments.empty')}
        </Typography.Paragraph>
      ) : null}
    </>
  )
}
