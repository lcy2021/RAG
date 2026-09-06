import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { I18nextProvider } from 'react-i18next'

import i18n from '../i18n'

export function renderWithI18n(ui: ReactElement, locale: 'zh' | 'en' = 'zh') {
  void i18n.changeLanguage(locale)
  return render(<I18nextProvider i18n={i18n}>{ui}</I18nextProvider>)
}
