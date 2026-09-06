import { Alert, Card, Col, Row, Statistic, Table, Tabs, Typography } from 'antd'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import {
  useExperimentUsage,
  useConversationUsage,
  useUsageSummary,
} from '../api/hooks'
import type { ConversationUsage, ExperimentUsage, UsageBucket } from '../api/types'
import { ListPageHeader } from '../components/ListPageHeader'
import { matchesQuery } from '../lib/matchesQuery'
import { formatRelativeTime, sessionLabel } from './chatContext'

function formatCost(value: number | null | undefined, empty: string): string {
  if (value == null) {
    return empty
  }
  return value.toLocaleString()
}

function formatTokens(value: number): string {
  return value.toLocaleString()
}

function BucketCards({
  total,
  chat,
  experiment,
}: {
  total: UsageBucket
  chat: UsageBucket
  experiment: UsageBucket
}) {
  const { t } = useTranslation()
  const empty = t('common.none')
  const cards = [
    { key: 'total', title: t('usage.total'), data: total },
    { key: 'chat', title: t('usage.chatScope'), data: chat },
    { key: 'experiment', title: t('usage.experimentScope'), data: experiment },
  ]
  return (
    <Row gutter={[16, 16]}>
      {cards.map((card) => (
        <Col key={card.key} xs={24} md={8}>
          <Card size="small" title={card.title}>
            <Row gutter={[12, 12]}>
              <Col span={12}>
                <Statistic title={t('usage.runs')} value={card.data.run_count} />
              </Col>
              <Col span={12}>
                <Statistic
                  title={t('usage.cost')}
                  value={card.data.cost_micros ?? empty}
                  suffix={card.data.cost_micros == null ? undefined : 'µ$'}
                />
              </Col>
              <Col span={12}>
                <Statistic title={t('usage.tokenIn')} value={formatTokens(card.data.token_in)} />
              </Col>
              <Col span={12}>
                <Statistic title={t('usage.tokenOut')} value={formatTokens(card.data.token_out)} />
              </Col>
              <Col span={12}>
                <Statistic
                  title={t('usage.tokenCached')}
                  value={formatTokens(card.data.token_cached)}
                />
              </Col>
            </Row>
          </Card>
        </Col>
      ))}
    </Row>
  )
}

export function UsagePage() {
  const { t } = useTranslation()
  const [tab, setTab] = useState('overview')
  const [query, setQuery] = useState('')
  const summary = useUsageSummary()
  const conversations = useConversationUsage()
  const experiments = useExperimentUsage()
  const empty = t('common.none')

  const conversationRows = useMemo(
    () =>
      (conversations.data ?? []).filter((row) =>
        matchesQuery(
          [
            row.title,
            row.conversation_id,
            sessionLabel({ id: row.conversation_id, title: row.title }),
          ],
          query,
        ),
      ),
    [conversations.data, query],
  )

  const experimentRows = useMemo(
    () =>
      (experiments.data ?? []).filter((row) =>
        matchesQuery([row.experiment_name, row.experiment_id], query),
      ),
    [experiments.data, query],
  )

  return (
    <>
      <ListPageHeader
        title={t('usage.title')}
        subtitle={t('usage.subtitle')}
        query={query}
        onQueryChange={setQuery}
      />
      <Alert
        type="info"
        showIcon
        style={{ marginTop: 12 }}
        message={t('usage.costFormulaTitle')}
        description={
          <div>
            <Typography.Paragraph style={{ marginBottom: 8 }}>
              <Typography.Text code>{t('usage.costFormula')}</Typography.Text>
            </Typography.Paragraph>
            <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
              {t('usage.costFormulaNote')}
            </Typography.Paragraph>
          </div>
        }
      />
      <Tabs
        style={{ marginTop: 8 }}
        activeKey={tab}
        onChange={setTab}
        items={[
          {
            key: 'overview',
            label: t('usage.tabOverview'),
            children: summary.isLoading ? (
              <Typography.Text type="secondary">{t('common.loading')}</Typography.Text>
            ) : summary.data ? (
              <BucketCards
                total={summary.data.total}
                chat={summary.data.chat}
                experiment={summary.data.experiment}
              />
            ) : (
              <Typography.Text type="secondary">{t('usage.empty')}</Typography.Text>
            ),
          },
          {
            key: 'conversations',
            label: t('usage.tabConversations'),
            children: (
              <Table<ConversationUsage>
                rowKey="conversation_id"
                size="small"
                loading={conversations.isLoading}
                dataSource={conversationRows}
                pagination={{ pageSize: 20, hideOnSinglePage: true }}
                locale={{ emptyText: t('usage.emptyConversations') }}
                columns={[
                  {
                    title: t('usage.conversation'),
                    render: (_, row) => (
                      <Link to={`/chat?c=${row.conversation_id}`}>
                        {sessionLabel({ id: row.conversation_id, title: row.title })}
                      </Link>
                    ),
                  },
                  {
                    title: t('usage.runs'),
                    dataIndex: 'run_count',
                    width: 90,
                  },
                  {
                    title: t('usage.tokenIn'),
                    dataIndex: 'token_in',
                    render: (value: number) => formatTokens(value),
                  },
                  {
                    title: t('usage.tokenOut'),
                    dataIndex: 'token_out',
                    render: (value: number) => formatTokens(value),
                  },
                  {
                    title: t('usage.tokenCached'),
                    dataIndex: 'token_cached',
                    render: (value: number) => formatTokens(value),
                  },
                  {
                    title: t('usage.cost'),
                    dataIndex: 'cost_micros',
                    render: (value: number | null) => formatCost(value, empty),
                  },
                  {
                    title: t('usage.lastRun'),
                    dataIndex: 'last_run_at',
                    render: (value: string | null) =>
                      value ? formatRelativeTime(value) : empty,
                  },
                ]}
              />
            ),
          },
          {
            key: 'experiments',
            label: t('usage.tabExperiments'),
            children: (
              <Table<ExperimentUsage>
                rowKey="experiment_id"
                size="small"
                loading={experiments.isLoading}
                dataSource={experimentRows}
                pagination={{ pageSize: 20, hideOnSinglePage: true }}
                locale={{ emptyText: t('usage.emptyExperiments') }}
                columns={[
                  {
                    title: t('usage.experiment'),
                    render: (_, row) => (
                      <Link to={`/experiments/${row.experiment_id}`}>{row.experiment_name}</Link>
                    ),
                  },
                  {
                    title: t('usage.evalRuns'),
                    dataIndex: 'eval_run_count',
                    width: 100,
                  },
                  {
                    title: t('usage.runs'),
                    dataIndex: 'run_count',
                    width: 90,
                  },
                  {
                    title: t('usage.tokenIn'),
                    dataIndex: 'token_in',
                    render: (value: number) => formatTokens(value),
                  },
                  {
                    title: t('usage.tokenOut'),
                    dataIndex: 'token_out',
                    render: (value: number) => formatTokens(value),
                  },
                  {
                    title: t('usage.tokenCached'),
                    dataIndex: 'token_cached',
                    render: (value: number) => formatTokens(value),
                  },
                  {
                    title: t('usage.cost'),
                    dataIndex: 'cost_micros',
                    render: (value: number | null) => formatCost(value, empty),
                  },
                  {
                    title: t('usage.lastRun'),
                    dataIndex: 'last_run_at',
                    render: (value: string | null) =>
                      value ? formatRelativeTime(value) : empty,
                  },
                ]}
              />
            ),
          },
        ]}
      />
    </>
  )
}
