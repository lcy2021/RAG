import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { App as AntApp } from 'antd'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AppLayout } from './components/AppLayout'
import { LocaleProvider } from './i18n/LocaleProvider'
import { ChatPage } from './pages/ChatPage'
import { CredentialCreatePage, CredentialEditPage } from './pages/CredentialFormPage'
import { CredentialsPage } from './pages/CredentialsPage'
import { ExperimentCreatePage } from './pages/ExperimentCreatePage'
import { ExperimentDetailPage } from './pages/ExperimentDetailPage'
import { ExperimentsPage } from './pages/ExperimentsPage'
import { KnowledgeBaseCreatePage } from './pages/KnowledgeBaseCreatePage'
import { KnowledgeBaseDetailPage } from './pages/KnowledgeBaseDetailPage'
import { KnowledgeBasesPage } from './pages/KnowledgeBasesPage'
import { PipelineCreatePage, PipelineEditPage } from './pages/PipelineEditorPage'
import { PipelinesPage } from './pages/PipelinesPage'
import { PluginsPage } from './pages/PluginsPage'
import { ScenarioCreatePage } from './pages/ScenarioCreatePage'
import { ScenarioDetailPage } from './pages/ScenarioDetailPage'
import { ScenariosPage } from './pages/ScenariosPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

export default function App() {
  return (
    <LocaleProvider>
      <AntApp style={{ height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <Routes>
              <Route element={<AppLayout />}>
                <Route path="/" element={<Navigate to="/credentials" replace />} />
                <Route path="/settings" element={<Navigate to="/credentials" replace />} />
                <Route
                  path="/settings/credentials/new"
                  element={<Navigate to="/credentials/new" replace />}
                />
                <Route path="/credentials" element={<CredentialsPage />} />
                <Route path="/credentials/new" element={<CredentialCreatePage />} />
                <Route path="/credentials/:id/edit" element={<CredentialEditPage />} />
                <Route path="/plugins" element={<PluginsPage />} />
                <Route path="/pipelines" element={<PipelinesPage />} />
                <Route path="/pipelines/new" element={<PipelineCreatePage />} />
                <Route path="/pipelines/:id/edit" element={<PipelineEditPage />} />
                <Route path="/kb" element={<KnowledgeBasesPage />} />
                <Route path="/kb/new" element={<KnowledgeBaseCreatePage />} />
                <Route path="/kb/:id" element={<KnowledgeBaseDetailPage />} />
                <Route path="/chat" element={<ChatPage />} />
                <Route path="/scenarios" element={<ScenariosPage />} />
                <Route path="/scenarios/new" element={<ScenarioCreatePage />} />
                <Route path="/scenarios/:id" element={<ScenarioDetailPage />} />
                <Route path="/experiments" element={<ExperimentsPage />} />
                <Route path="/experiments/new" element={<ExperimentCreatePage />} />
                <Route path="/experiments/:id" element={<ExperimentDetailPage />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </QueryClientProvider>
      </AntApp>
    </LocaleProvider>
  )
}
