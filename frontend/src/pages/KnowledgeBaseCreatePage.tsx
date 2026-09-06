import { Button, Card, Form, Input, Select } from 'antd'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { useCreateKnowledgeBase, usePipelines } from '../api/hooks'
import { FormPageHeader } from '../components/FormPageHeader'
import { useMessage } from '../hooks/useMessage'

export function KnowledgeBaseCreatePage() {
  const { t } = useTranslation()
  const message = useMessage()
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const pipelines = usePipelines()
  const create = useCreateKnowledgeBase()
  const ingestPipelines = (pipelines.data ?? []).filter((item) => item.kind === 'ingest')

  return (
    <>
      <FormPageHeader title={t('kb.createTitle')} backTo="/kb" />
      <Card>
        <Form
          form={form}
          layout="vertical"
          style={{ maxWidth: 520 }}
          onFinish={async (values: {
            name: string
            description?: string
            ingest_pipeline_id: string
          }) => {
            try {
              const kb = await create.mutateAsync({
                name: values.name,
                description: values.description || null,
                ingest_pipeline_id: values.ingest_pipeline_id,
              })
              message.success(t('kb.created'))
              navigate(`/kb/${kb.id}`)
            } catch (error) {
              message.error(error instanceof Error ? error.message : t('common.createFailed'))
            }
          }}
        >
          <Form.Item name="name" label={t('common.name')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label={t('common.description')}>
            <Input />
          </Form.Item>
          <Form.Item
            name="ingest_pipeline_id"
            label={t('kb.ingestPipeline')}
            rules={[{ required: true, message: t('kb.ingestPipelineRequired') }]}
          >
            <Select
              options={ingestPipelines.map((item) => ({ value: item.id, label: item.name }))}
            />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={create.isPending}>
            {t('common.create')}
          </Button>
        </Form>
      </Card>
    </>
  )
}
