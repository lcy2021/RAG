import { Button, Popconfirm, Table } from 'antd'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'

import { useDeleteKnowledgeBase, useKnowledgeBases } from '../api/hooks'
import { ListPageHeader } from '../components/ListPageHeader'
import { useMessage } from '../hooks/useMessage'
import { matchesQuery } from '../lib/matchesQuery'

export function KnowledgeBasesPage() {
  const { t } = useTranslation()
  const message = useMessage()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const kbs = useKnowledgeBases()
  const remove = useDeleteKnowledgeBase()
  const rows = useMemo(
    () =>
      (kbs.data ?? []).filter((row) =>
        matchesQuery(
          [row.name, row.description, ...row.collections.map((item) => item.name)],
          query,
        ),
      ),
    [kbs.data, query],
  )

  return (
    <>
      <ListPageHeader
        title={t('kb.title')}
        subtitle={t('kb.subtitle')}
        query={query}
        onQueryChange={setQuery}
        onAdd={() => navigate('/kb/new')}
      />
      <Table
        style={{ marginTop: 16 }}
        rowKey="id"
        size="small"
        loading={kbs.isLoading}
        dataSource={rows}
        pagination={false}
        columns={[
          {
            title: t('common.name'),
            dataIndex: 'name',
            render: (name: string, row) => <Link to={`/kb/${row.id}`}>{name}</Link>,
          },
          { title: t('common.description'), dataIndex: 'description' },
          {
            title: t('kb.collection'),
            render: (_, row) =>
              row.collections.map((item) => item.name).join(', ') || t('common.none'),
          },
          {
            title: '',
            width: 80,
            render: (_, row) => (
              <Popconfirm
                title={t('kb.deleteConfirm')}
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
