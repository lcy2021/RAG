import { ArrowLeftOutlined } from '@ant-design/icons'
import { Button } from 'antd'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

type FormPageHeaderProps = {
  title: string
  backTo: string
}

export function FormPageHeader({ title, backTo }: FormPageHeaderProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  return (
    <div className="page-header" style={{ marginBottom: 16 }}>
      <Button
        type="link"
        className="page-back"
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate(backTo)}
      >
        {t('common.back')}
      </Button>
      <h1 className="page-header-title">{title}</h1>
    </div>
  )
}
