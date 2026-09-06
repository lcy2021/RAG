import { ConfigProvider, theme } from 'antd'
import enUS from 'antd/locale/en_US'
import zhCN from 'antd/locale/zh_CN'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { AppLocale } from './index'

const ANT_LOCALES = {
  zh: zhCN,
  en: enUS,
} as const

const FONT =
  '"DM Sans", "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif'

type LocaleProviderProps = {
  children: ReactNode
}

export function LocaleProvider({ children }: LocaleProviderProps) {
  const { i18n } = useTranslation()
  const locale = (i18n.resolvedLanguage === 'en' ? 'en' : 'zh') as AppLocale

  return (
    <ConfigProvider
      locale={ANT_LOCALES[locale]}
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: '#5e6ad2',
          colorInfo: '#5e6ad2',
          colorSuccess: '#3dd68c',
          colorWarning: '#f5a524',
          colorError: '#f76166',
          colorBgBase: '#010102',
          colorBgContainer: '#141516',
          colorBgElevated: '#18191a',
          colorBgLayout: '#010102',
          colorBorder: '#23252a',
          colorBorderSecondary: '#1c1d1f',
          colorText: '#f7f8f8',
          colorTextSecondary: '#8a8f98',
          colorTextTertiary: '#62666d',
          colorTextQuaternary: '#4a4e56',
          colorLink: '#828fff',
          colorLinkHover: '#a0a8ff',
          borderRadius: 8,
          borderRadiusLG: 12,
          borderRadiusSM: 6,
          fontFamily: FONT,
          fontSize: 13,
          controlHeight: 32,
          controlHeightLG: 36,
          controlHeightSM: 28,
          motionDurationMid: '0.15s',
          wireframe: false,
        },
        components: {
          Layout: {
            siderBg: '#0f1011',
            headerBg: '#0f1011',
            bodyBg: '#010102',
            triggerBg: '#141516',
            headerHeight: 52,
            headerPadding: '0 20px',
          },
          Menu: {
            darkItemBg: 'transparent',
            darkSubMenuItemBg: 'transparent',
            darkItemSelectedBg: 'rgba(94, 106, 210, 0.16)',
            darkItemHoverBg: 'rgba(255, 255, 255, 0.04)',
            darkItemSelectedColor: '#f7f8f8',
            darkItemColor: '#8a8f98',
            itemBorderRadius: 6,
            itemMarginInline: 8,
            itemHeight: 34,
            iconSize: 15,
            fontSize: 13,
          },
          Table: {
            headerBg: 'transparent',
            headerSplitColor: 'transparent',
            rowHoverBg: '#1c1d1f',
            borderColor: '#23252a',
            cellPaddingBlockSM: 10,
            cellPaddingInlineSM: 12,
          },
          Button: {
            primaryShadow: 'none',
            dangerShadow: 'none',
            defaultShadow: 'none',
            fontWeight: 500,
          },
          Input: {
            activeShadow: '0 0 0 2px rgba(94, 106, 210, 0.28)',
            hoverBorderColor: '#34343a',
          },
          Select: {
            optionSelectedBg: 'rgba(94, 106, 210, 0.16)',
          },
          Card: {
            colorBgContainer: '#18191a',
          },
          Tabs: {
            inkBarColor: '#5e6ad2',
            itemSelectedColor: '#f7f8f8',
            itemColor: '#8a8f98',
            itemHoverColor: '#f7f8f8',
          },
          Tag: {
            defaultBg: '#1c1d1f',
            defaultColor: '#8a8f98',
          },
          Modal: {
            contentBg: '#18191a',
            headerBg: '#18191a',
          },
          Dropdown: {
            colorBgElevated: '#18191a',
          },
          Tooltip: {
            colorBgSpotlight: '#222326',
          },
          Segmented: {
            trackBg: '#0f1011',
            itemSelectedBg: '#222326',
          },
        },
      }}
    >
      {children}
    </ConfigProvider>
  )
}
