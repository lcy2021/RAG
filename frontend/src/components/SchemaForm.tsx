import { Input, InputNumber, Select, Switch, Typography } from 'antd'
import { useTranslation } from 'react-i18next'

import { isForbiddenParamKey } from '../constants'
import type { JsonSchema } from '../api/types'

type SchemaFormProps = {
  schema: JsonSchema | undefined
  value: Record<string, unknown>
  onChange: (next: Record<string, unknown>) => void
  bindingOptions?: Array<{ value: string; label: string }>
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

/** Show control characters as JSON escapes so tags like \\n\\n are editable. */
export function encodeStringTag(value: string): string {
  if (value === '') {
    return '(empty)'
  }
  return JSON.stringify(value).slice(1, -1)
}

export function decodeStringTag(value: string): string {
  if (value === '(empty)') {
    return ''
  }
  try {
    return JSON.parse(`"${value}"`) as string
  } catch {
    return value
  }
}

export function SchemaForm({ schema, value, onChange, bindingOptions }: SchemaFormProps) {
  const { t } = useTranslation()
  const properties = schema?.properties ?? {}
  const keys = Object.keys(properties).filter((key) => !isForbiddenParamKey(key))

  if (keys.length === 0) {
    return <Typography.Text type="secondary">{t('schema.noParams')}</Typography.Text>
  }

  const setField = (key: string, fieldValue: unknown) => {
    const next = { ...value }
    if (fieldValue === undefined || fieldValue === null || fieldValue === '') {
      delete next[key]
    } else {
      next[key] = fieldValue
    }
    onChange(next)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {keys.map((key) => {
        const fieldSchema = properties[key] ?? {}
        const fieldType = fieldSchema.type
        const current = value[key]
        const isBinding = key === 'binding_id' && bindingOptions && bindingOptions.length > 0

        if (isBinding) {
          return (
            <label key={key}>
              <FieldLabel name={key} />
              <Select
                allowClear
                style={{ width: '100%' }}
                value={typeof current === 'string' ? current : undefined}
                options={bindingOptions}
                onChange={(next) => setField(key, next)}
                placeholder={t('schema.pickCredential')}
              />
            </label>
          )
        }

        if (fieldSchema.enum && fieldSchema.enum.length > 0) {
          return (
            <label key={key}>
              <FieldLabel name={key} />
              <Select
                allowClear
                style={{ width: '100%' }}
                value={current as string | number | undefined}
                options={fieldSchema.enum.map((item) => ({
                  value: item,
                  label: String(item),
                }))}
                onChange={(next) => setField(key, next)}
              />
            </label>
          )
        }

        if (fieldType === 'boolean') {
          return (
            <label key={key} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Switch checked={Boolean(current)} onChange={(checked) => setField(key, checked)} />
              <FieldLabel name={key} />
            </label>
          )
        }

        if (fieldType === 'integer' || fieldType === 'number') {
          return (
            <label key={key}>
              <FieldLabel name={key} />
              <InputNumber
                style={{ width: '100%' }}
                value={typeof current === 'number' ? current : undefined}
                onChange={(next) => setField(key, next)}
              />
            </label>
          )
        }

        if (fieldType === 'array' && fieldSchema.items?.type === 'string') {
          const tags = Array.isArray(current) ? current.map((item) => encodeStringTag(String(item))) : []
          return (
            <label key={key}>
              <FieldLabel name={key} />
              <Select
                mode="tags"
                style={{ width: '100%' }}
                value={tags}
                onChange={(next) =>
                  setField(
                    key,
                    next.length > 0 ? next.map(decodeStringTag) : undefined,
                  )
                }
                placeholder={t('schema.addTag')}
                tokenSeparators={[',']}
              />
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {t('schema.stringTagsHint')}
              </Typography.Text>
            </label>
          )
        }

        if (fieldType === 'object' && isRecord(current)) {
          return (
            <div key={key}>
              <FieldLabel name={key} />
              <SchemaForm
                schema={fieldSchema}
                value={current}
                onChange={(nested) => setField(key, nested)}
                bindingOptions={bindingOptions}
              />
            </div>
          )
        }

        return (
          <label key={key}>
            <FieldLabel name={key} />
            <Input
              value={current == null ? '' : String(current)}
              onChange={(event) => setField(key, event.target.value)}
            />
          </label>
        )
      })}
    </div>
  )
}

function FieldLabel({ name }: { name: string }) {
  return <Typography.Text style={{ display: 'block', marginBottom: 4 }}>{name}</Typography.Text>
}
