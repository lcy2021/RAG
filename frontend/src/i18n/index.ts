import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import en from './locales/en.json'
import zh from './locales/zh.json'

export const LOCALE_STORAGE_KEY = 'raglab.locale'
export const SUPPORTED_LOCALES = ['zh', 'en'] as const
export type AppLocale = (typeof SUPPORTED_LOCALES)[number]

export function resolveInitialLocale(): AppLocale {
  if (typeof window !== 'undefined') {
    const stored = window.localStorage.getItem(LOCALE_STORAGE_KEY)
    if (stored === 'zh' || stored === 'en') {
      return stored
    }
    const browser = window.navigator.language.toLowerCase()
    if (browser.startsWith('zh')) {
      return 'zh'
    }
  }
  return 'zh'
}

void i18n.use(initReactI18next).init({
  resources: {
    zh: { translation: zh },
    en: { translation: en },
  },
  lng: resolveInitialLocale(),
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
})

export default i18n
