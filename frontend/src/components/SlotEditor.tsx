import { Card, Radio, Select, Space, Typography } from 'antd'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { Credential, PluginSummary, SlotMode } from '../api/types'
import { credentialKindForStage } from '../constants'
import { SchemaForm } from './SchemaForm'

export type SlotBindingState = {
  name: string
  params: Record<string, unknown>
}

export type SlotState = {
  mode: SlotMode
  bindings: SlotBindingState[]
}

type SlotEditorProps = {
  stage: string
  plugins: PluginSummary[]
  credentials: Credential[]
  value: SlotState | null
  onChange: (value: SlotState | null) => void
  optional?: boolean
  /** When true, offer single vs hybrid (ensemble) mode. */
  allowEnsemble?: boolean
}

function bindingOptions(plugins: PluginSummary[]) {
  return plugins.map((plugin) => ({
    value: plugin.name,
    label: `${plugin.name} (${plugin.version})`,
    description: plugin.description,
  }))
}

function PluginOptionLabel({
  label,
  description,
}: {
  label: ReactNode
  description?: string
}) {
  return (
    <div style={{ padding: '2px 0', whiteSpace: 'normal' }}>
      <div>{label}</div>
      {description ? (
        <Typography.Text type="secondary" style={{ fontSize: 12, lineHeight: 1.4 }}>
          {description}
        </Typography.Text>
      ) : null}
    </div>
  )
}

function defaultBinding(plugins: PluginSummary[], name: string): SlotBindingState {
  const plugin = plugins.find((item) => item.name === name)
  return { name, params: { ...(plugin?.default_params ?? {}) } }
}

export function SlotEditor({
  stage,
  plugins,
  credentials,
  value,
  onChange,
  optional = false,
  allowEnsemble = false,
}: SlotEditorProps) {
  const { t } = useTranslation()
  const mode: SlotMode = value?.mode ?? 'first'
  const bindings = value?.bindings ?? []
  const primary = bindings[0]
  const kind = credentialKindForStage(stage)
  const credOptions = credentials
    .filter((item) => (kind ? item.kind === kind : true))
    .map((item) => ({
      value: item.id,
      label: `${item.name} (${item.model_name})`,
    }))

  const setFirstPlugin = (name: string | undefined) => {
    if (!name) {
      onChange(null)
      return
    }
    onChange({ mode: 'first', bindings: [defaultBinding(plugins, name)] })
  }

  const setEnsemblePlugins = (names: string[]) => {
    if (names.length === 0) {
      onChange(null)
      return
    }
    const previous = new Map(bindings.map((item) => [item.name, item]))
    onChange({
      mode: 'ensemble',
      bindings: names.map((name) => previous.get(name) ?? defaultBinding(plugins, name)),
    })
  }

  const updateBindingParams = (name: string, params: Record<string, unknown>) => {
    if (!value) {
      return
    }
    onChange({
      ...value,
      bindings: value.bindings.map((item) => (item.name === name ? { ...item, params } : item)),
    })
  }

  return (
    <Card size="small" title={`${t(`stages.${stage}`, { defaultValue: stage })} · ${stage}`}>
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        {stage === 'reranker' ? (
          <Typography.Text type="secondary">{t('slot.rerankHint')}</Typography.Text>
        ) : null}
        {allowEnsemble ? (
          <Radio.Group
            value={mode}
            optionType="button"
            onChange={(event) => {
              const next = event.target.value as SlotMode
              if (next === 'ensemble') {
                const preferred = ['dense', 'bm25'].filter((name) =>
                  plugins.some((plugin) => plugin.name === name),
                )
                const names =
                  preferred.length >= 2
                    ? preferred
                    : plugins.slice(0, 2).map((plugin) => plugin.name)
                setEnsemblePlugins(names)
                return
              }
              const keep = bindings[0]?.name ?? plugins[0]?.name
              setFirstPlugin(keep)
            }}
          >
            <Radio.Button value="first">{t('slot.modeFirst')}</Radio.Button>
            <Radio.Button value="ensemble">{t('slot.modeEnsemble')}</Radio.Button>
          </Radio.Group>
        ) : null}

        {mode === 'ensemble' && allowEnsemble ? (
          <>
            <Typography.Text type="secondary">{t('slot.hybridHint')}</Typography.Text>
            <Select
              mode="multiple"
              allowClear={optional}
              placeholder={t('slot.pickPlugins')}
              style={{ width: '100%' }}
              value={bindings.map((item) => item.name)}
              options={bindingOptions(plugins)}
              optionRender={(option) => (
                <PluginOptionLabel
                  label={option.label}
                  description={option.data.description as string | undefined}
                />
              )}
              onChange={(names) => setEnsemblePlugins(names)}
            />
            {bindings.map((binding) => {
              const selected = plugins.find((plugin) => plugin.name === binding.name)
              if (!selected) {
                return null
              }
              return (
                <Card key={binding.name} size="small" type="inner" title={binding.name}>
                  {selected.description ? (
                    <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
                      {selected.description}
                    </Typography.Paragraph>
                  ) : null}
                  <SchemaForm
                    schema={selected.config_schema}
                    value={binding.params}
                    onChange={(params) => updateBindingParams(binding.name, params)}
                    bindingOptions={credOptions}
                  />
                </Card>
              )
            })}
            {bindings.length < 2 ? (
              <Typography.Text type="warning">{t('slot.ensembleNeedTwo')}</Typography.Text>
            ) : null}
          </>
        ) : (
          <>
            <Select
              allowClear={optional}
              placeholder={t('slot.pickPlugin')}
              style={{ width: '100%' }}
              value={primary?.name}
              options={bindingOptions(plugins)}
              optionRender={(option) => (
                <PluginOptionLabel
                  label={option.label}
                  description={option.data.description as string | undefined}
                />
              )}
              onChange={(name) => setFirstPlugin(name)}
            />
            {primary ? (
              (() => {
                const selected = plugins.find((plugin) => plugin.name === primary.name)
                if (!selected) {
                  return (
                    <Typography.Text type="secondary">{t('slot.needPlugin')}</Typography.Text>
                  )
                }
                return (
                  <>
                    {selected.description ? (
                      <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                        {selected.description}
                      </Typography.Paragraph>
                    ) : null}
                    <SchemaForm
                      schema={selected.config_schema}
                      value={primary.params}
                      onChange={(params) => updateBindingParams(primary.name, params)}
                      bindingOptions={credOptions}
                    />
                  </>
                )
              })()
            ) : (
              <Typography.Text type="secondary">
                {optional ? t('slot.skipStage') : t('slot.needPlugin')}
              </Typography.Text>
            )}
          </>
        )}
      </Space>
    </Card>
  )
}
