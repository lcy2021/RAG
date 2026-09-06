import { PlusOutlined } from '@ant-design/icons'
import { Button, Input } from 'antd'
import { useTranslation } from 'react-i18next'

type ListPageHeaderProps = {
  title: string
  subtitle?: string
  query: string
  onQueryChange: (value: string) => void
  onAdd?: () => void
  addLabel?: string
}

export function ListPageHeader({
  title,
  subtitle,
  query,
  onQueryChange,
  onAdd,
  addLabel,
}: ListPageHeaderProps) {
  const { t } = useTranslation()
  return (
    <div className="page-header">
      <h1 className="page-header-title">{title}</h1>
      {subtitle ? <p className="page-header-subtitle">{subtitle}</p> : null}
      <div className="page-toolbar">
        <Input.Search
          allowClear
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          onSearch={onQueryChange}
          placeholder={t('common.searchPlaceholder')}
          style={{ width: 280 }}
        />
        {onAdd ? (
          <Button type="primary" icon={<PlusOutlined />} onClick={onAdd}>
            {addLabel ?? t('common.add')}
          </Button>
        ) : null}
      </div>
    </div>
  )
}
