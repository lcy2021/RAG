import { Button, Card, Form, Input, InputNumber, Select } from 'antd'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { useCreateScenario, useKnowledgeBases, usePlugins } from '../api/hooks'
import { FormPageHeader } from '../components/FormPageHeader'
import { useMessage } from '../hooks/useMessage'

type FormValues = {
  name: string
  knowledge_base_id: string
  metric_plugins: string[]
  notes?: string
  latency_p95_ms_max?: number | null
  cost_micros_max?: number | null
}

export function ScenarioCreatePage() {
  const { t } = useTranslation()
  const message = useMessage()
  const navigate = useNavigate()
  const [form] = Form.useForm<FormValues>()
  const kbs = useKnowledgeBases()
  const plugins = usePlugins()
  const create = useCreateScenario()
  const evaluators = useMemo(
    () => (plugins.data ?? []).filter((item) => item.stage === 'evaluator'),
    [plugins.data],
  )

  return (
    <>
      <FormPageHeader title={t('scenarios.createTitle')} backTo="/scenarios" />
      <Card>
        <Form
          form={form}
          layout="vertical"
          style={{ maxWidth: 560 }}
          initialValues={{ metric_plugins: ['recall_at_k', 'mrr'] }}
          onFinish={async (values) => {
            try {
              const weights: Record<string, number> = {}
              for (const name of values.metric_plugins) {
                weights[name] = 1
              }
              const scenario = await create.mutateAsync({
                name: values.name,
                knowledge_base_id: values.knowledge_base_id,
                metric_plugins: values.metric_plugins,
                metric_weights: weights,
                latency_p95_ms_max: values.latency_p95_ms_max ?? null,
                cost_micros_max: values.cost_micros_max ?? null,
                notes: values.notes || null,
              })
              message.success(t('scenarios.created'))
              navigate(`/scenarios/${scenario.id}`)
            } catch (error) {
              message.error(error instanceof Error ? error.message : t('common.createFailed'))
            }
          }}
        >
          <Form.Item name="name" label={t('common.name')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item
            name="knowledge_base_id"
            label={t('scenarios.knowledgeBase')}
            rules={[{ required: true, message: t('scenarios.kbRequired') }]}
          >
            <Select
              options={(kbs.data ?? []).map((item) => ({ value: item.id, label: item.name }))}
              placeholder={t('kb.pickKb')}
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
            <Input.TextArea rows={3} />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={create.isPending}>
            {t('common.create')}
          </Button>
        </Form>
      </Card>
    </>
  )
}
