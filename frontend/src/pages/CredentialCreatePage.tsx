import { Button, Card, Form, Input, InputNumber, Radio } from 'antd'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { useCreateCredential } from '../api/hooks'
import type { CredentialKind } from '../api/types'
import { FormPageHeader } from '../components/FormPageHeader'
import { useMessage } from '../hooks/useMessage'

export function CredentialCreatePage() {
  const { t } = useTranslation()
  const message = useMessage()
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const kind = Form.useWatch('kind', form) as CredentialKind | undefined
  const create = useCreateCredential()

  return (
    <>
      <FormPageHeader title={t('settings.addCredential')} backTo="/settings" />
      <Card>
        <Form
          form={form}
          layout="vertical"
          style={{ maxWidth: 520 }}
          initialValues={{ kind: 'vector', provider: 'openai' }}
          onFinish={async (values: {
            name: string
            kind: CredentialKind
            model_name: string
            secret: string
            base_url?: string
            dim?: number
          }) => {
            try {
              await create.mutateAsync({
                name: values.name,
                kind: values.kind,
                model_name: values.model_name,
                secret: values.secret,
                provider: 'openai',
                base_url: values.base_url || null,
                extra: values.kind === 'vector' && values.dim ? { dim: values.dim } : {},
              })
              message.success(t('settings.credentialSaved'))
              navigate('/settings')
            } catch (error) {
              message.error(error instanceof Error ? error.message : t('common.saveFailed'))
            }
          }}
        >
          <Form.Item name="name" label={t('common.name')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="kind" label={t('settings.kind')} rules={[{ required: true }]}>
            <Radio.Group>
              <Radio.Button value="vector">{t('settings.kind_vector')}</Radio.Button>
              <Radio.Button value="llm">{t('settings.kind_llm')}</Radio.Button>
            </Radio.Group>
          </Form.Item>
          <Form.Item name="model_name" label={t('settings.model')} rules={[{ required: true }]}>
            <Input
              placeholder={
                kind === 'llm' ? 'gpt-4o-mini' : 'text-embedding-3-small'
              }
            />
          </Form.Item>
          <Form.Item name="base_url" label={t('settings.baseUrl')}>
            <Input placeholder="https://api.openai.com/v1" />
          </Form.Item>
          <Form.Item name="secret" label={t('settings.secret')} rules={[{ required: true }]}>
            <Input.Password autoComplete="off" />
          </Form.Item>
          {kind === 'vector' ? (
            <Form.Item name="dim" label={t('settings.dim')}>
              <InputNumber min={1} style={{ width: '100%' }} />
            </Form.Item>
          ) : null}
          <Button type="primary" htmlType="submit" loading={create.isPending}>
            {t('common.save')}
          </Button>
        </Form>
      </Card>
    </>
  )
}
