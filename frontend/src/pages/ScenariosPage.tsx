import { Button, Popconfirm, Space, Table, Tag, Typography } from 'antd'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'

import { useDeleteScenario, useKnowledgeBases, useScenarios } from '../api/hooks'
import { ListPageHeader } from '../components/ListPageHeader'
import { useMessage } from '../hooks/useMessage'
import { matchesQuery } from '../lib/matchesQuery'

export function ScenariosPage() {
  const { t } = useTranslation()
  const message = useMessage()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const scenarios = useScenarios()
  const kbs = useKnowledgeBases()
  const remove = useDeleteScenario()
  const kbName = useMemo(() => {
    const map = new Map((kbs.data ?? []).map((row) => [row.id, row.name]))
    return (id: string) => map.get(id) ?? id.slice(0, 8)
  }, [kbs.data])
  const rows = useMemo(
    () =>
      (scenarios.data ?? []).filter((row) =>
        matchesQuery([row.name, row.notes, kbName(row.knowledge_base_id), ...row.metric_plugins], query),
      ),
    [scenarios.data, query, kbName],
  )

  return (
    <>
      <ListPageHeader
        title={t('scenarios.title')}
        subtitle={t('scenarios.subtitle')}
        query={query}
        onQueryChange={setQuery}
        onAdd={() => navigate('/scenarios/new')}
      />
      <Table
        style={{ marginTop: 16 }}
        rowKey="id"
        size="small"
        loading={scenarios.isLoading}
        dataSource={rows}
        pagination={false}
        columns={[
          {
            title: t('common.name'),
            dataIndex: 'name',
            render: (name: string, row) => <Link to={`/scenarios/${row.id}`}>{name}</Link>,
          },
          {
            title: t('scenarios.knowledgeBase'),
            render: (_, row) => kbName(row.knowledge_base_id),
          },
          {
            title: t('scenarios.metrics'),
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
            title: t('scenarios.itemCount'),
            dataIndex: 'item_count',
            width: 100,
          },
          {
            title: '',
            width: 80,
            render: (_, row) => (
              <Popconfirm
                title={t('scenarios.deleteConfirm')}
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
      {!scenarios.isLoading && rows.length === 0 ? (
        <Typography.Paragraph type="secondary" style={{ marginTop: 12 }}>
          {t('scenarios.empty')}
        </Typography.Paragraph>
      ) : null}
    </>
  )
}
