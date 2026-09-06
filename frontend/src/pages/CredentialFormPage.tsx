import { Button, Card, Form, Input, InputNumber, Radio, Spin } from 'antd'
import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import {
  useCreateCredential,
  useCredential,
  useUpdateCredential,
} from '../api/hooks'
import type { CredentialKind } from '../api/types'
import { FormPageHeader } from '../components/FormPageHeader'
import { useMessage } from '../hooks/useMessage'

type FormValues = {
  name: string
  kind: CredentialKind
  model_name: string
  secret?: string
  base_url?: string
  dim?: number
}

function CredentialFormPage({ mode }: { mode: 'create' | 'edit' }) {
  const { t } = useTranslation()
  const message = useMessage()
  const navigate = useNavigate()
  const { id = '' } = useParams()
  const [form] = Form.useForm<FormValues>()
  const kind = Form.useWatch('kind', form) as CredentialKind | undefined
  const create = useCreateCredential()
  const update = useUpdateCredential()
  const existing = useCredential(mode === 'edit' ? id : null)

  useEffect(() => {
    if (mode !== 'edit' || !existing.data) {
      return
    }
    const dim = existing.data.extra?.dim
    form.setFieldsValue({
      name: existing.data.name,
      kind: existing.data.kind,
      model_name: existing.data.model_name,
      base_url: existing.data.base_url ?? undefined,
      dim: typeof dim === 'number' ? dim : 1536,
      secret: undefined,
    })
  }, [existing.data, form, mode])

  if (mode === 'edit' && existing.isLoading) {
    return <Spin />
  }

  if (mode === 'edit' && existing.isError) {
    return <Card>{t('common.saveFailed')}</Card>
  }

  return (
    <>
      <FormPageHeader
        title={mode === 'create' ? t('credentials.add') : t('credentials.edit')}
        backTo="/credentials"
      />
      <Card>
        <Form
          form={form}
          layout="vertical"
          style={{ maxWidth: 520 }}
          initialValues={
            mode === 'create' ? { kind: 'vector', provider: 'openai', dim: 1536 } : undefined
          }
          onFinish={async (values: FormValues) => {
            const extra =
              values.kind === 'vector' ? { dim: values.dim ?? 1536 } : {}
            try {
              if (mode === 'create') {
                await create.mutateAsync({
                  name: values.name,
                  kind: values.kind,
                  model_name: values.model_name,
                  secret: values.secret ?? '',
                  provider: 'openai',
                  base_url: values.base_url || null,
                  extra,
                })
              } else {
                await update.mutateAsync({
                  id,
                  body: {
                    name: values.name,
                    kind: values.kind,
                    model_name: values.model_name,
                    secret: values.secret?.trim() ? values.secret : null,
                    provider: 'openai',
                    base_url: values.base_url || null,
                    extra,
                  },
                })
              }
              message.success(t('credentials.saved'))
              navigate('/credentials')
            } catch (error) {
              message.error(error instanceof Error ? error.message : t('common.saveFailed'))
            }
          }}
        >
          <Form.Item name="name" label={t('common.name')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="kind" label={t('credentials.kind')} rules={[{ required: true }]}>
            <Radio.Group>
              <Radio.Button value="vector">{t('credentials.kind_vector')}</Radio.Button>
              <Radio.Button value="llm">{t('credentials.kind_llm')}</Radio.Button>
            </Radio.Group>
          </Form.Item>
          <Form.Item name="model_name" label={t('credentials.model')} rules={[{ required: true }]}>
            <Input
              placeholder={kind === 'llm' ? 'gpt-4o-mini' : 'text-embedding-3-small'}
            />
          </Form.Item>
          <Form.Item name="base_url" label={t('credentials.baseUrl')}>
            <Input placeholder="https://api.openai.com/v1" />
          </Form.Item>
          <Form.Item
            name="secret"
            label={t('credentials.secret')}
            extra={mode === 'edit' ? t('credentials.secretKeepHint') : undefined}
            rules={mode === 'create' ? [{ required: true }] : undefined}
          >
            <Input.Password
              autoComplete="off"
              placeholder={
                mode === 'edit' && existing.data?.key_hint
                  ? t('credentials.secretPlaceholder', { hint: existing.data.key_hint })
                  : undefined
              }
            />
          </Form.Item>
          {kind === 'vector' ? (
            <Form.Item
              name="dim"
              label={t('credentials.dim')}
              rules={[{ required: true, message: t('common.required') }]}
            >
              <InputNumber min={1} style={{ width: '100%' }} />
            </Form.Item>
          ) : null}
          <Button
            type="primary"
            htmlType="submit"
            loading={create.isPending || update.isPending}
          >
            {t('common.save')}
          </Button>
        </Form>
      </Card>
    </>
  )
}

export function CredentialCreatePage() {
  return <CredentialFormPage mode="create" />
}

export function CredentialEditPage() {
  return <CredentialFormPage mode="edit" />
}
