import {
  ApiOutlined,
  AppstoreOutlined,
  CommentOutlined,
  DatabaseOutlined,
  ExperimentOutlined,
  KeyOutlined,
  NodeIndexOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import { Layout, Menu, Space, Typography } from 'antd'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, Outlet, useLocation } from 'react-router-dom'

import { useHealth } from '../api/hooks'
import brandMark from '../assets/rag-lab-brand.png'
import { NAV_ITEMS } from '../constants'
import { LanguageSwitch } from './LanguageSwitch'
import './AppLayout.css'

const ICONS: Record<string, ReactNode> = {
  '/credentials': <KeyOutlined />,
  '/plugins': <AppstoreOutlined />,
  '/pipelines': <NodeIndexOutlined />,
  '/kb': <DatabaseOutlined />,
  '/scenarios': <ThunderboltOutlined />,
  '/experiments': <ExperimentOutlined />,
  '/chat': <CommentOutlined />,
}

const NAV_LABEL_KEYS: Record<string, string> = {
  '/credentials': 'nav.credentials',
  '/plugins': 'nav.plugins',
  '/pipelines': 'nav.pipelines',
  '/kb': 'nav.kb',
  '/scenarios': 'nav.scenarios',
  '/experiments': 'nav.experiments',
  '/chat': 'nav.chat',
}

export function AppLayout() {
  const { t } = useTranslation()
  const location = useLocation()
  const health = useHealth()
  const selected =
    NAV_ITEMS.find(
      (item) => location.pathname === item.key || location.pathname.startsWith(`${item.key}/`),
    )?.key ?? '/credentials'
  const isChat = location.pathname === '/chat' || location.pathname.startsWith('/chat/')
  const apiOk = health.data?.status === 'ok'
  const dbOk = health.data?.database === 'ok'

  return (
    <Layout className="app-shell">
      <Layout.Sider
        className="app-sider"
        breakpoint="lg"
        collapsedWidth={64}
        width={232}
        theme="dark"
      >
        <div className="app-brand">
          <img className="app-brand-mark" src={brandMark} alt="" aria-hidden />
          <span className="app-brand-text">{t('layout.brand')}</span>
        </div>
        <Menu
          className="app-menu"
          theme="dark"
          mode="inline"
          selectedKeys={[selected]}
          items={NAV_ITEMS.map((item) => ({
            key: item.key,
            icon: ICONS[item.key],
            label: <Link to={item.key}>{t(NAV_LABEL_KEYS[item.key] ?? item.key)}</Link>,
          }))}
        />
        <div className="app-sider-footer">
          <div className={`app-status-chip ${apiOk && dbOk ? 'is-ok' : 'is-warn'}`}>
            <ApiOutlined />
            <span>
              API {health.data?.status ?? '…'} · DB {health.data?.database ?? '…'}
            </span>
          </div>
          {health.data?.version ? (
            <Typography.Text className="app-version" type="secondary">
              {health.data.version}
            </Typography.Text>
          ) : null}
        </div>
      </Layout.Sider>
      <Layout className="app-main">
        <Layout.Header className="app-header">
          <Typography.Text className="app-tagline">{t('layout.tagline')}</Typography.Text>
          <Space size={12} align="center">
            <LanguageSwitch />
          </Space>
        </Layout.Header>
        <Layout.Content className={isChat ? 'app-content is-chat' : 'app-content'}>
          <Outlet />
        </Layout.Content>
      </Layout>
    </Layout>
  )
}
