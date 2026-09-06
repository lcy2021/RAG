import { Button, Popconfirm, Table } from 'antd'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'

import { useDeletePipeline, usePipelines } from '../api/hooks'
import { ListPageHeader } from '../components/ListPageHeader'
import { useMessage } from '../hooks/useMessage'
import { matchesQuery } from '../lib/matchesQuery'

export function PipelinesPage() {
  const { t } = useTranslation()
  const message = useMessage()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const pipelines = usePipelines()
  const remove = useDeletePipeline()
  const rows = useMemo(
    () =>
      (pipelines.data ?? []).filter((row) =>
        matchesQuery(
          [
            row.name,
            row.kind,
            row.description,
            ...row.slots.flatMap((slot) => slot.bindings.map((binding) => binding.name)),
          ],
          query,
        ),
      ),
    [pipelines.data, query],
  )

  return (
    <>
      <ListPageHeader
        title={t('pipelines.title')}
        subtitle={t('pipelines.subtitle')}
        query={query}
        onQueryChange={setQuery}
        onAdd={() => navigate('/pipelines/new')}
        addLabel={t('common.add')}
      />
      <Table
        style={{ marginTop: 16 }}
        rowKey="id"
        size="small"
        loading={pipelines.isLoading}
        dataSource={rows}
        pagination={false}
        columns={[
          {
            title: t('common.name'),
            dataIndex: 'name',
            filters: [...new Set((pipelines.data ?? []).map((item) => item.name))]
              .sort((a, b) => a.localeCompare(b))
              .map((name) => ({ text: name, value: name })),
            onFilter: (value, row) => row.name === value,
            render: (name: string, row) => <Link to={`/pipelines/${row.id}/edit`}>{name}</Link>,
          },
          { title: t('common.type'), dataIndex: 'kind', width: 90 },
          {
            title: t('pipelines.slots'),
            render: (_, row) =>
              row.slots
                .map((slot) => {
                  const names = slot.bindings.map((binding) => binding.name).join('+')
                  const label = names || '?'
                  return slot.mode === 'ensemble'
                    ? `${slot.stage}:[${label}]`
                    : `${slot.stage}:${label}`
                })
                .join(' → '),
          },
          {
            title: '',
            width: 80,
            render: (_, row) => (
              <Popconfirm
                title={t('pipelines.deleteConfirm')}
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
    </>
  )
}
