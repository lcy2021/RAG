import { GlobalOutlined } from '@ant-design/icons'
import { Select } from 'antd'
import { useTranslation } from 'react-i18next'

import { LOCALE_STORAGE_KEY, type AppLocale } from '../i18n'

export function LanguageSwitch() {
  const { t, i18n } = useTranslation()
  const value = (i18n.resolvedLanguage === 'en' ? 'en' : 'zh') as AppLocale

  return (
    <Select
      size="small"
      variant="borderless"
      value={value}
      popupMatchSelectWidth={false}
      style={{ minWidth: 96 }}
      suffixIcon={<GlobalOutlined />}
      aria-label={t('layout.language')}
      options={[
        { value: 'zh', label: '中文' },
        { value: 'en', label: 'English' },
      ]}
      onChange={async (next: AppLocale) => {
        window.localStorage.setItem(LOCALE_STORAGE_KEY, next)
        await i18n.changeLanguage(next)
        document.documentElement.lang = next === 'zh' ? 'zh-CN' : 'en'
      }}
    />
  )
}
