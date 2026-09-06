import { App } from 'antd'

/** Prefer this over static `message` so toasts respect App/ConfigProvider theme. */
export function useMessage() {
  return App.useApp().message
}
