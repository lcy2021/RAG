import { Button, Card, Form, Input, Select } from 'antd'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import {
  useCreateExperiment,
  useCredentials,
  usePipelines,
  useScenarios,
} from '../api/hooks'
import { FormPageHeader } from '../components/FormPageHeader'
import { useMessage } from '../hooks/useMessage'

type FormValues = {
  name: string
  scenario_id: string
  query_pipeline_ids: string[]
  judge_binding_id?: string
  notes?: string
}

export function ExperimentCreatePage() {
  const { t } = useTranslation()
  const message = useMessage()
  const navigate = useNavigate()
  const [form] = Form.useForm<FormValues>()
  const scenarios = useScenarios()
  const pipelines = usePipelines()
  const credentials = useCredentials()
  const create = useCreateExperiment()
  const scenarioId = Form.useWatch('scenario_id', form)
  const queryPipelines = useMemo(
    () => (pipelines.data ?? []).filter((item) => item.kind === 'query'),
    [pipelines.data],
  )
  const pipelineById = useMemo(
    () => new Map(queryPipelines.map((item) => [item.id, item])),
    [queryPipelines],
  )
  const selectedScenario = useMemo(
    () => (scenarios.data ?? []).find((item) => item.id === scenarioId),
    [scenarioId, scenarios.data],
  )
  const needsJudge = Boolean(selectedScenario?.metric_plugins?.includes('faithfulness'))
  const llmCredentials = useMemo(
    () => (credentials.data ?? []).filter((item) => item.kind === 'llm'),
    [credentials.data],
  )

  return (
    <>
      <FormPageHeader title={t('experiments.createTitle')} backTo="/experiments" />
      <Card>
        <Form
          form={form}
          layout="vertical"
          style={{ maxWidth: 720 }}
          initialValues={{ query_pipeline_ids: [] }}
          onFinish={async (values) => {
            try {
              const pipelineIds = values.query_pipeline_ids
              if (pipelineIds.length < 2) {
                message.error(t('experiments.pipelinesMin'))
                return
              }
              const usedLabels = new Set<string>()
              const variants = pipelineIds.map((pipelineId) => {
                const pipeline = pipelineById.get(pipelineId)
                const baseLabel = (pipeline?.name || pipelineId.slice(0, 8)).trim()
                let label = baseLabel
                let suffix = 2
                while (usedLabels.has(label)) {
                  label = `${baseLabel}-${suffix}`
                  suffix += 1
                }
                usedLabels.add(label)
                return {
                  label,
                  query_pipeline_id: pipelineId,
                  slot_overrides: {},
                }
              })
              const experiment = await create.mutateAsync({
                name: values.name,
                scenario_id: values.scenario_id,
                query_pipeline_id: pipelineIds[0],
                variants,
                judge_binding_id: values.judge_binding_id || null,
                notes: values.notes || null,
              })
              message.success(t('experiments.created'))
              navigate(`/experiments/${experiment.id}`)
            } catch (error) {
              message.error(error instanceof Error ? error.message : t('common.createFailed'))
            }
          }}
        >
          <Form.Item name="name" label={t('common.name')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item
            name="scenario_id"
            label={t('experiments.scenario')}
            rules={[{ required: true, message: t('experiments.scenarioRequired') }]}
          >
            <Select
              options={(scenarios.data ?? []).map((item) => ({
                value: item.id,
                label: `${item.name} (${item.item_count} items)`,
              }))}
            />
          </Form.Item>
          <Form.Item
            name="query_pipeline_ids"
            label={t('experiments.pipelines')}
            extra={t('experiments.pipelinesHint')}
            rules={[
              { required: true, message: t('experiments.pipelinesRequired') },
              {
                validator: async (_, value: string[] | undefined) => {
                  if (!value || value.length < 2) {
                    throw new Error(t('experiments.pipelinesMin'))
                  }
                },
              },
            ]}
          >
            <Select
              mode="multiple"
              optionFilterProp="label"
              placeholder={t('experiments.pipelinesPlaceholder')}
              options={queryPipelines.map((item) => ({
                value: item.id,
                label: item.name,
              }))}
            />
          </Form.Item>
          {needsJudge ? (
            <Form.Item
              name="judge_binding_id"
              label={t('experiments.judgeBinding')}
              extra={t('experiments.judgeBindingHint')}
              rules={[{ required: true, message: t('experiments.judgeBindingRequired') }]}
            >
              <Select
                allowClear
                placeholder={t('experiments.judgeBindingPlaceholder')}
                options={llmCredentials.map((item) => ({
                  value: item.id,
                  label: `${item.name} (${item.model_name})`,
                }))}
              />
            </Form.Item>
          ) : null}
          <Form.Item name="notes" label={t('experiments.notes')}>
            <Input.TextArea rows={2} />
          </Form.Item>

          <div style={{ marginTop: 8 }}>
            <Button type="primary" htmlType="submit" loading={create.isPending}>
              {t('common.create')}
            </Button>
          </div>
        </Form>
      </Card>
    </>
  )
}
