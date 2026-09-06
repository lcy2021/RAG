import { Button, Popconfirm, Space, Table } from 'antd'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { useCredentials, useDeleteCredential } from '../api/hooks'
import { ListPageHeader } from '../components/ListPageHeader'
import { useMessage } from '../hooks/useMessage'
import { matchesQuery } from '../lib/matchesQuery'

export function CredentialsPage() {
  const { t } = useTranslation()
  const message = useMessage()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const list = useCredentials()
  const remove = useDeleteCredential()
  const rows = useMemo(
    () =>
      (list.data ?? []).filter((row) =>
        matchesQuery(
          [row.name, row.kind, row.model_name, row.provider, row.base_url, row.key_hint],
          query,
        ),
      ),
    [list.data, query],
  )

  return (
    <>
      <ListPageHeader
        title={t('credentials.title')}
        subtitle={t('credentials.subtitle')}
        query={query}
        onQueryChange={setQuery}
        onAdd={() => navigate('/credentials/new')}
      />
      <Table
        style={{ marginTop: 16 }}
        rowKey="id"
        size="small"
        loading={list.isLoading}
        dataSource={rows}
        pagination={false}
        columns={[
          { title: t('common.name'), dataIndex: 'name' },
          {
            title: t('credentials.kind'),
            dataIndex: 'kind',
            width: 100,
            render: (kind: string) => t(`credentials.kind_${kind}`, { defaultValue: kind }),
          },
          { title: t('credentials.model'), dataIndex: 'model_name' },
          {
            title: t('credentials.baseUrl'),
            dataIndex: 'base_url',
            render: (value: string | null) => value || t('common.none'),
          },
          {
            title: t('credentials.keyHint'),
            dataIndex: 'key_hint',
            render: (value: string | null) => value || t('common.none'),
          },
          {
            title: '',
            width: 140,
            render: (_, row) => (
              <Space size={0}>
                <Button type="link" size="small" onClick={() => navigate(`/credentials/${row.id}/edit`)}>
                  {t('common.edit')}
                </Button>
                <Popconfirm
                  title={t('credentials.deleteConfirm')}
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
              </Space>
            ),
          },
        ]}
      />
    </>
  )
}
