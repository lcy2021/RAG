import { Button, Card, Form, Input, Radio, Space, Spin } from 'antd'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import {
  useCreatePipeline,
  useCredentials,
  usePipeline,
  usePlugins,
  useUpdatePipeline,
} from '../api/hooks'
import type { Pipeline, PipelineKind, PluginSummary } from '../api/types'
import { FormPageHeader } from '../components/FormPageHeader'
import { SlotEditor, type SlotState } from '../components/SlotEditor'
import { defaultPluginForStage, stagesForKind } from '../constants'
import { useMessage } from '../hooks/useMessage'

const ENSEMBLE_STAGES = new Set(['retriever'])

function initialSlots(
  kind: PipelineKind,
  plugins: PluginSummary[],
): Record<string, SlotState | null> {
  const next: Record<string, SlotState | null> = {}
  for (const stage of stagesForKind(kind)) {
    if (kind === 'query' && stage === 'retriever') {
      const dense = plugins.find((plugin) => plugin.stage === stage && plugin.name === 'dense')
      const bm25 = plugins.find((plugin) => plugin.stage === stage && plugin.name === 'bm25')
      if (dense && bm25) {
        next[stage] = {
          mode: 'ensemble',
          bindings: [
            { name: dense.name, params: { ...dense.default_params } },
            { name: bm25.name, params: { ...bm25.default_params } },
          ],
        }
        continue
      }
    }
    const preferred = defaultPluginForStage(kind, stage)
    const match = plugins.find((plugin) => plugin.stage === stage && plugin.name === preferred)
    next[stage] = match
      ? { mode: 'first', bindings: [{ name: match.name, params: { ...match.default_params } }] }
      : null
  }
  return next
}

function slotsFromPipeline(pipeline: Pipeline): Record<string, SlotState | null> {
  const next: Record<string, SlotState | null> = {}
  for (const stage of stagesForKind(pipeline.kind)) {
    const slot = pipeline.slots.find((item) => item.stage === stage)
    if (!slot || slot.bindings.length === 0) {
      next[stage] = null
      continue
    }
    next[stage] = {
      mode: slot.mode,
      bindings: slot.bindings.map((binding) => ({
        name: binding.name,
        params: { ...binding.params },
      })),
    }
  }
  return next
}

type PipelineEditorPageProps = {
  mode: 'create' | 'edit'
}

export function PipelineEditorPage({ mode }: PipelineEditorPageProps) {
  const { t } = useTranslation()
  const message = useMessage()
  const navigate = useNavigate()
  const { id: pipelineId } = useParams<{ id: string }>()
  const isEdit = mode === 'edit'
  const [kind, setKind] = useState<PipelineKind>('ingest')
  const [slotDraft, setSlotDraft] = useState<Record<string, SlotState | null> | null>(null)
  const [hydratedId, setHydratedId] = useState<string | null>(null)
  const plugins = usePlugins()
  const credentials = useCredentials()
  const existing = usePipeline(isEdit ? (pipelineId ?? null) : null)
  const create = useCreatePipeline()
  const update = useUpdatePipeline()
  const [form] = Form.useForm()

  const pluginList = plugins.data
  const slots =
    slotDraft ?? (pluginList && pluginList.length > 0 ? initialSlots(kind, pluginList) : {})

  useEffect(() => {
    if (!isEdit || !existing.data || !pipelineId || hydratedId === pipelineId) {
      return
    }
    form.setFieldsValue({
      name: existing.data.name,
      description: existing.data.description ?? undefined,
    })
    setKind(existing.data.kind)
    setSlotDraft(slotsFromPipeline(existing.data))
    setHydratedId(pipelineId)
  }, [existing.data, form, hydratedId, isEdit, pipelineId])

  const byStage = (stage: string) => (pluginList ?? []).filter((plugin) => plugin.stage === stage)
  const optionalStages = new Set(['grader', 'compressor'])
  const saving = create.isPending || update.isPending
  const loading = isEdit && (existing.isLoading || hydratedId !== pipelineId)

  if (isEdit && existing.isError) {
    return (
      <>
        <FormPageHeader title={t('pipelines.editTitle')} backTo="/pipelines" />
        <Card>{t('pipelines.notFound')}</Card>
      </>
    )
  }

  return (
    <>
      <FormPageHeader
        title={isEdit ? t('pipelines.editTitle') : t('pipelines.createTitle')}
        backTo="/pipelines"
      />
      <Card>
        <Spin spinning={Boolean(loading)}>
          <Form
            form={form}
            layout="vertical"
            style={{ maxWidth: 720 }}
            onFinish={async (values: { name: string; description?: string }) => {
              for (const stage of stagesForKind(kind)) {
                const slot = slots[stage]
                if (slot?.mode === 'ensemble' && slot.bindings.length < 2) {
                  message.error(t('slot.ensembleNeedTwo'))
                  return
                }
              }
              const selectedSlots = stagesForKind(kind)
                .map((stage, ordinal) => {
                  const slot = slots[stage]
                  if (!slot || slot.bindings.length === 0) {
                    return null
                  }
                  const mode =
                    slot.mode === 'ensemble' && slot.bindings.length > 1 ? 'ensemble' : 'first'
                  return {
                    stage,
                    mode: mode as 'first' | 'ensemble',
                    ordinal,
                    bindings: slot.bindings.map((binding) => ({
                      name: binding.name,
                      params: binding.params,
                    })),
                  }
                })
                .filter((item) => item !== null)
              if (selectedSlots.length === 0) {
                message.error(t('pipelines.needSlot'))
                return
              }
              try {
                if (isEdit && pipelineId) {
                  await update.mutateAsync({
                    id: pipelineId,
                    body: {
                      name: values.name,
                      description: values.description || null,
                      slots: selectedSlots,
                    },
                  })
                  message.success(t('pipelines.updated'))
                } else {
                  await create.mutateAsync({
                    name: values.name,
                    kind,
                    description: values.description || null,
                    slots: selectedSlots,
                  })
                  message.success(t('pipelines.created'))
                }
                navigate('/pipelines')
              } catch (error) {
                message.error(error instanceof Error ? error.message : t('common.saveFailed'))
              }
            }}
          >
            <Form.Item name="name" label={t('common.name')} rules={[{ required: true }]}>
              <Input />
            </Form.Item>
            <Form.Item name="description" label={t('common.description')}>
              <Input.TextArea rows={2} />
            </Form.Item>
            <Form.Item label={t('common.type')}>
              <Radio.Group
                value={kind}
                disabled={isEdit}
                onChange={(event) => {
                  const next = event.target.value as PipelineKind
                  setKind(next)
                  setSlotDraft(pluginList ? initialSlots(next, pluginList) : null)
                }}
              >
                <Radio.Button value="ingest">{t('pipelines.ingest')}</Radio.Button>
                <Radio.Button value="query">{t('pipelines.query')}</Radio.Button>
              </Radio.Group>
            </Form.Item>
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              {stagesForKind(kind).map((stage) => (
                <SlotEditor
                  key={stage}
                  stage={stage}
                  plugins={byStage(stage)}
                  credentials={credentials.data ?? []}
                  value={slots[stage] ?? null}
                  optional={optionalStages.has(stage)}
                  allowEnsemble={ENSEMBLE_STAGES.has(stage)}
                  onChange={(value) => setSlotDraft({ ...slots, [stage]: value })}
                />
              ))}
            </Space>
            <Button type="primary" htmlType="submit" loading={saving} style={{ marginTop: 16 }}>
              {t('pipelines.save')}
            </Button>
          </Form>
        </Spin>
      </Card>
    </>
  )
}

export function PipelineCreatePage() {
  return <PipelineEditorPage mode="create" />
}

export function PipelineEditPage() {
  return <PipelineEditorPage mode="edit" />
}
