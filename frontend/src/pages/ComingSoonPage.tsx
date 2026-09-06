import { Alert } from 'antd'
import { useTranslation } from 'react-i18next'

type ComingSoonPageProps = {
  title: string
  milestone: string
  description: string
}

export function ComingSoonPage({ title, milestone, description }: ComingSoonPageProps) {
  const { t } = useTranslation()
  return (
    <>
      <div className="page-header" style={{ marginBottom: 16 }}>
        <h1 className="page-header-title">{title}</h1>
      </div>
      <Alert
        type="info"
        showIcon
        message={t('comingSoon.notReady', { milestone })}
        description={description}
      />
    </>
  )
}
