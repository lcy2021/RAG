import {
  Button,
  Card,
  Checkbox,
  Form,
  Input,
  InputNumber,
  Popconfirm,
  Select,
  Space,
  Table,
  Typography,
  Upload,
} from 'antd'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import {
  useCreateEvalItem,
  useCreateEvalSpan,
  useDeleteEvalItem,
  useDeleteEvalSpan,
  useDocuments,
  useImportScenarioItems,
  useKnowledgeBases,
  usePlugins,
  useScenario,
  useUpdateScenario,
} from '../api/hooks'
import type { EvalItem } from '../api/types'
import { FormPageHeader } from '../components/FormPageHeader'
import { useMessage } from '../hooks/useMessage'
import {
  downloadScenarioCsvTemplate,
  downloadScenarioJsonTemplate,
} from '../lib/scenarioImport'

type SettingsFormValues = {
  name: string
  metric_plugins: string[]
  notes?: string
  latency_p95_ms_max?: number | null
  cost_micros_max?: number | null
}

export function ScenarioDetailPage() {
  const { t } = useTranslation()
  const message = useMessage()
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const scenario = useScenario(id ?? null)
  const kbs = useKnowledgeBases()
  const plugins = usePlugins()
  const documents = useDocuments(scenario.data?.knowledge_base_id ?? null)
  const updateScenario = useUpdateScenario()
  const createItem = useCreateEvalItem(id ?? '')
  const importItems = useImportScenarioItems(id ?? '')
  const deleteItem = useDeleteEvalItem(id ?? '')
  const createSpan = useCreateEvalSpan(id ?? '')
  const deleteSpan = useDeleteEvalSpan(id ?? '')
  const [settingsForm] = Form.useForm<SettingsFormValues>()
  const [itemForm] = Form.useForm<{ question: string; expected?: string }>()
  const [replaceOnImport, setReplaceOnImport] = useState(false)
  const [settingsHydratedId, setSettingsHydratedId] = useState<string | null>(null)
  const [spanForms, setSpanForms] = useState<Record<string, { document_id?: string; quote?: string }>>(
    {},
  )

  const evaluators = useMemo(
    () => (plugins.data ?? []).filter((item) => item.stage === 'evaluator'),
    [plugins.data],
  )
  const kbName =
    (kbs.data ?? []).find((row) => row.id === scenario.data?.knowledge_base_id)?.name ??
    scenario.data?.knowledge_base_id

  useEffect(() => {
    if (!scenario.data || settingsHydratedId === scenario.data.id) {
      return
    }
    settingsForm.setFieldsValue({
      name: scenario.data.name,
      metric_plugins: scenario.data.metric_plugins,
      notes: scenario.data.notes ?? undefined,
      latency_p95_ms_max: scenario.data.latency_p95_ms_max,
      cost_micros_max: scenario.data.cost_micros_max,
    })
    setSettingsHydratedId(scenario.data.id)
  }, [scenario.data, settingsForm, settingsHydratedId])

  if (scenario.isLoading) {
    return (
      <>
        <FormPageHeader title={t('scenarios.title')} backTo="/scenarios" />
        <Typography.Text type="secondary">{t('common.loading')}</Typography.Text>
      </>
    )
  }

  if (!scenario.data) {
    return (
      <>
        <FormPageHeader title={t('scenarios.title')} backTo="/scenarios" />
        <Typography.Text type="secondary">{t('scenarios.notFound')}</Typography.Text>
        <Button type="link" onClick={() => navigate('/scenarios')}>
          {t('common.back')}
        </Button>
      </>
    )
  }

  const detail = scenario.data

  return (
    <>
      <FormPageHeader title={detail.name} backTo="/scenarios" />
      <Card title={t('scenarios.settingsTitle')} style={{ marginBottom: 16 }}>
        <Form
          form={settingsForm}
          layout="vertical"
          style={{ maxWidth: 640 }}
          onFinish={async (values) => {
            try {
              const weights: Record<string, number> = {}
              for (const name of values.metric_plugins) {
                weights[name] = detail.metric_weights?.[name] ?? 1
              }
              await updateScenario.mutateAsync({
                id: detail.id,
                body: {
                  name: values.name,
                  metric_plugins: values.metric_plugins,
                  metric_weights: weights,
                  latency_p95_ms_max: values.latency_p95_ms_max ?? null,
                  cost_micros_max: values.cost_micros_max ?? null,
                  notes: values.notes || null,
                },
              })
              message.success(t('scenarios.updated'))
            } catch (error) {
              message.error(error instanceof Error ? error.message : t('common.saveFailed'))
            }
          }}
        >
          <Form.Item name="name" label={t('common.name')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item
            label={t('scenarios.knowledgeBase')}
            extra={t('scenarios.kbImmutableHint')}
          >
            <Select
              disabled
              value={detail.knowledge_base_id}
              options={[{ value: detail.knowledge_base_id, label: kbName }]}
            />
          </Form.Item>
          <Form.Item
            name="metric_plugins"
            label={t('scenarios.metrics')}
            rules={[{ required: true, message: t('scenarios.metricsRequired') }]}
          >
            <Select
              mode="multiple"
              options={evaluators.map((item) => ({
                value: item.name,
                label: `${item.name}${item.description ? ` — ${item.description}` : ''}`,
              }))}
            />
          </Form.Item>
          <Form.Item name="latency_p95_ms_max" label={t('scenarios.latencySlo')}>
            <InputNumber min={1} style={{ width: '100%' }} placeholder={t('common.optional')} />
          </Form.Item>
          <Form.Item name="cost_micros_max" label={t('scenarios.costSlo')}>
            <InputNumber min={1} style={{ width: '100%' }} placeholder={t('common.optional')} />
          </Form.Item>
          <Form.Item name="notes" label={t('scenarios.notes')}>
            <Input.TextArea rows={3} placeholder={t('common.optional')} />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={updateScenario.isPending}>
            {t('common.save')}
          </Button>
        </Form>
      </Card>

      <Card title={t('scenarios.itemsTitle')} style={{ marginBottom: 16 }}>
        <div
          style={{
            marginBottom: 16,
            padding: 12,
            background: 'rgba(0,0,0,0.02)',
            borderRadius: 8,
          }}
        >
          <Typography.Paragraph type="secondary" style={{ marginBottom: 8 }}>
            {t('scenarios.importHint')}
          </Typography.Paragraph>
          <Space wrap>
            <Upload
              accept=".csv,.json,text/csv,application/json"
              showUploadList={false}
              beforeUpload={(file) => {
                importItems.mutate(
                  { file, replace: replaceOnImport },
                  {
                    onSuccess: (result) => {
                      const base = t('scenarios.importDone', {
                        items: result.created_items,
                        spans: result.created_spans,
                      })
                      if (result.warnings?.length) {
                        message.warning(
                          `${base} · ${t('scenarios.importWarnings', {
                            count: result.warnings.length,
                          })}`,
                        )
                      } else {
                        message.success(base)
                      }
                    },
                    onError: (error) =>
                      message.error(
                        error instanceof Error ? error.message : t('scenarios.importFailed'),
                      ),
                  },
                )
                return false
              }}
            >
              <Button type="primary" loading={importItems.isPending}>
                {t('scenarios.importFile')}
              </Button>
            </Upload>
            <Button onClick={() => downloadScenarioCsvTemplate()}>
              {t('scenarios.downloadCsvTemplate')}
            </Button>
            <Button onClick={() => downloadScenarioJsonTemplate()}>
              {t('scenarios.downloadJsonTemplate')}
            </Button>
            <Checkbox
              checked={replaceOnImport}
              onChange={(event) => setReplaceOnImport(event.target.checked)}
            >
              {t('scenarios.importReplace')}
            </Checkbox>
          </Space>
        </div>

        <Form
          form={itemForm}
          layout="vertical"
          style={{ maxWidth: 640, marginBottom: 16 }}
          onFinish={async (values) => {
            try {
              await createItem.mutateAsync({
                question: values.question,
                expected: values.expected || null,
              })
              itemForm.resetFields()
              message.success(t('scenarios.itemCreated'))
            } catch (error) {
              message.error(error instanceof Error ? error.message : t('common.createFailed'))
            }
          }}
        >
          <Form.Item
            name="question"
            label={t('scenarios.question')}
            rules={[{ required: true, message: t('scenarios.questionRequired') }]}
          >
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="expected" label={t('scenarios.expected')}>
            <Input.TextArea rows={2} placeholder={t('common.optional')} />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={createItem.isPending}>
            {t('scenarios.addItem')}
          </Button>
        </Form>

        <Table
          rowKey="id"
          size="small"
          loading={
            createItem.isPending || deleteItem.isPending || importItems.isPending
          }
          dataSource={detail.items}
          pagination={false}
          expandable={{
            expandedRowRender: (item: EvalItem) => (
              <div>
                <Typography.Paragraph type="secondary" style={{ marginBottom: 8 }}>
                  {t('scenarios.spansHint')}
                </Typography.Paragraph>
                <Space direction="vertical" style={{ width: '100%' }} size="middle">
                  {(item.spans ?? []).map((span) => {
                    const docTitle =
                      (documents.data ?? []).find((doc) => doc.id === span.document_id)?.title ||
                      span.document_id.slice(0, 8)
                    return (
                      <Space key={span.id} align="start" style={{ width: '100%' }}>
                        <Typography.Text style={{ flex: 1 }}>
                          <Typography.Text type="secondary">[{docTitle}] </Typography.Text>
                          {span.quote}
                        </Typography.Text>
                        <Popconfirm
                          title={t('scenarios.deleteSpanConfirm')}
                          onConfirm={async () => {
                            try {
                              await deleteSpan.mutateAsync({ itemId: item.id, spanId: span.id })
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
                    )
                  })}
                  <Space wrap align="start">
                    <Select
                      style={{ width: 220 }}
                      placeholder={t('scenarios.pickDocument')}
                      value={spanForms[item.id]?.document_id}
                      options={(documents.data ?? []).map((doc) => ({
                        value: doc.id,
                        label: doc.title || doc.source_uri,
                      }))}
                      onChange={(value) =>
                        setSpanForms((prev) => ({
                          ...prev,
                          [item.id]: { ...prev[item.id], document_id: value },
                        }))
                      }
                    />
                    <Input.TextArea
                      style={{ width: 360 }}
                      rows={2}
                      placeholder={t('scenarios.quotePlaceholder')}
                      value={spanForms[item.id]?.quote}
                      onChange={(event) =>
                        setSpanForms((prev) => ({
                          ...prev,
                          [item.id]: { ...prev[item.id], quote: event.target.value },
                        }))
                      }
                    />
                    <Button
                      loading={createSpan.isPending}
                      onClick={async () => {
                        const draft = spanForms[item.id]
                        if (!draft?.document_id || !(draft.quote || '').trim()) {
                          message.error(t('scenarios.spanRequired'))
                          return
                        }
                        try {
                          await createSpan.mutateAsync({
                            itemId: item.id,
                            body: {
                              document_id: draft.document_id,
                              quote: draft.quote!.trim(),
                            },
                          })
                          setSpanForms((prev) => ({
                            ...prev,
                            [item.id]: { document_id: draft.document_id, quote: '' },
                          }))
                          message.success(t('scenarios.spanCreated'))
                        } catch (error) {
                          message.error(
                            error instanceof Error ? error.message : t('common.createFailed'),
                          )
                        }
                      }}
                    >
                      {t('scenarios.addSpan')}
                    </Button>
                  </Space>
                </Space>
              </div>
            ),
          }}
          columns={[
            {
              title: t('scenarios.question'),
              dataIndex: 'question',
              ellipsis: true,
            },
            {
              title: t('scenarios.expected'),
              dataIndex: 'expected',
              ellipsis: true,
              render: (value: string | null) => value || t('common.none'),
            },
            {
              title: t('scenarios.spanCount'),
              width: 90,
              render: (_, row) => row.spans?.length ?? 0,
            },
            {
              title: '',
              width: 80,
              render: (_, row) => (
                <Popconfirm
                  title={t('scenarios.deleteItemConfirm')}
                  onConfirm={async () => {
                    try {
                      await deleteItem.mutateAsync(row.id)
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
      </Card>
    </>
  )
}
