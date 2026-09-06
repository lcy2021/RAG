import { Table, Tag } from 'antd'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { usePlugins } from '../api/hooks'
import { ListPageHeader } from '../components/ListPageHeader'
import { matchesQuery } from '../lib/matchesQuery'

export function PluginsPage() {
  const { t } = useTranslation()
  const [query, setQuery] = useState('')
  const plugins = usePlugins()
  const rows = useMemo(
    () =>
      (plugins.data ?? []).filter((row) =>
        matchesQuery(
          [
            row.name,
            row.description,
            row.stage,
            row.version,
            row.source,
            t(`stages.${row.stage}`, { defaultValue: row.stage }),
          ],
          query,
        ),
      ),
    [plugins.data, query, t],
  )

  return (
    <>
      <ListPageHeader
        title={t('plugins.title')}
        subtitle={t('plugins.subtitle')}
        query={query}
        onQueryChange={setQuery}
      />
      <Table
        style={{ marginTop: 16 }}
        rowKey={(row) => `${row.stage}:${row.name}:${row.version}`}
        loading={plugins.isLoading}
        dataSource={rows}
        pagination={false}
        columns={[
          {
            title: t('plugins.stage'),
            dataIndex: 'stage',
            filters: [...new Set((plugins.data ?? []).map((item) => item.stage))].map((stage) => ({
              text: t(`stages.${stage}`, { defaultValue: stage }),
              value: stage,
            })),
            onFilter: (value, row) => row.stage === value,
            render: (stage: string) => t(`stages.${stage}`, { defaultValue: stage }),
          },
          { title: t('common.name'), dataIndex: 'name', width: 160 },
          {
            title: t('common.description'),
            dataIndex: 'description',
            ellipsis: true,
            render: (value: string) => value || t('common.none'),
          },
          { title: t('plugins.version'), dataIndex: 'version', width: 90 },
          {
            title: t('plugins.source'),
            dataIndex: 'source',
            width: 100,
            render: (source: string) => (
              <Tag color={source === 'builtin' ? 'blue' : 'purple'}>{source}</Tag>
            ),
          },
          {
            title: t('plugins.paramFields'),
            width: 200,
            ellipsis: true,
            render: (_, row) =>
              Object.keys(row.config_schema.properties ?? {}).join(', ') || t('common.none'),
          },
        ]}
      />
    </>
  )
}
