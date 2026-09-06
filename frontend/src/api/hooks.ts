import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiDelete, apiGet, apiPost, apiPut, apiUpload, apiUploadForm, streamChatMessage } from './client'
import type {
  ChatMessage,
  ChatStreamMeta,
  Conversation,
  Credential,
  CredentialCreate,
  CredentialUpdate,
  Document,
  EvalItem,
  EvalItemCreate,
  EvalItemSpan,
  EvalItemSpanCreate,
  EvalRun,
  EvalRunDetail,
  Experiment,
  ExperimentCreate,
  HealthResponse,
  IngestJob,
  KnowledgeBase,
  KnowledgeBaseCreate,
  Pipeline,
  PipelineCreate,
  PipelineProgressEvent,
  PipelineUpdate,
  PluginSummary,
  Promotion,
  RagRunSources,
  Scenario,
  ScenarioCreate,
  ScenarioDetail,
  ScenarioItemsImportResult,
  ScenarioUpdate,
  UsageSummary,
  ConversationUsage,
  ExperimentUsage,
} from './types'

export const queryKeys = {
  health: ['health'] as const,
  plugins: ['plugins'] as const,
  credentials: ['credentials'] as const,
  pipelines: ['pipelines'] as const,
  pipeline: (id: string) => ['pipelines', id] as const,
  knowledgeBases: ['knowledge-bases'] as const,
  knowledgeBase: (id: string) => ['knowledge-bases', id] as const,
  documents: (kbId: string) => ['knowledge-bases', kbId, 'documents'] as const,
  scenarios: ['scenarios'] as const,
  scenario: (id: string) => ['scenarios', id] as const,
  experiments: ['experiments'] as const,
  experiment: (id: string) => ['experiments', id] as const,
  experimentRuns: (id: string) => ['experiments', id, 'runs'] as const,
  experimentRun: (experimentId: string, runId: string) =>
    ['experiments', experimentId, 'runs', runId] as const,
  conversations: ['conversations'] as const,
  messages: (id: string) => ['conversations', id, 'messages'] as const,
  runSources: (conversationId: string, ragRunId: string) =>
    ['conversations', conversationId, 'rag-runs', ragRunId, 'sources'] as const,
  usageSummary: ['usage', 'summary'] as const,
  usageConversations: ['usage', 'conversations'] as const,
  usageExperiments: ['usage', 'experiments'] as const,
}

export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: () => apiGet<HealthResponse>('/health'),
    refetchInterval: 30_000,
  })
}

export function usePlugins() {
  return useQuery({
    queryKey: queryKeys.plugins,
    queryFn: () => apiGet<PluginSummary[]>('/plugins'),
  })
}

export function useCredentials() {
  return useQuery({
    queryKey: queryKeys.credentials,
    queryFn: () => apiGet<Credential[]>('/settings/credentials'),
  })
}

export function useCredential(id: string | null) {
  return useQuery({
    queryKey: [...queryKeys.credentials, id],
    queryFn: () => apiGet<Credential>(`/settings/credentials/${id}`),
    enabled: Boolean(id),
  })
}

export function useCreateCredential() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: CredentialCreate) => apiPost<Credential>('/settings/credentials', body),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.credentials }),
  })
}

export function useUpdateCredential() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: CredentialUpdate }) =>
      apiPut<Credential>(`/settings/credentials/${id}`, body),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.credentials }),
  })
}

export function useDeleteCredential() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiDelete(`/settings/credentials/${id}`),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.credentials }),
  })
}

export function usePipelines() {
  return useQuery({
    queryKey: queryKeys.pipelines,
    queryFn: () => apiGet<Pipeline[]>('/pipelines'),
  })
}

export function usePipeline(id: string | null) {
  return useQuery({
    queryKey: queryKeys.pipeline(id ?? ''),
    queryFn: () => apiGet<Pipeline>(`/pipelines/${id}`),
    enabled: Boolean(id),
  })
}

export function useCreatePipeline() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: PipelineCreate) => apiPost<Pipeline>('/pipelines', body),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.pipelines }),
  })
}

export function useUpdatePipeline() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: PipelineUpdate }) =>
      apiPut<Pipeline>(`/pipelines/${id}`, body),
    onSuccess: (_data, vars) => {
      client.invalidateQueries({ queryKey: queryKeys.pipelines })
      client.invalidateQueries({ queryKey: queryKeys.pipeline(vars.id) })
    },
  })
}

export function useDeletePipeline() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiDelete(`/pipelines/${id}`),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.pipelines }),
  })
}

export function useKnowledgeBases() {
  return useQuery({
    queryKey: queryKeys.knowledgeBases,
    queryFn: () => apiGet<KnowledgeBase[]>('/knowledge-bases'),
  })
}

export function useCreateKnowledgeBase() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: KnowledgeBaseCreate) => apiPost<KnowledgeBase>('/knowledge-bases', body),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.knowledgeBases }),
  })
}

export function useDeleteKnowledgeBase() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiDelete(`/knowledge-bases/${id}`),
    onMutate: async (id) => {
      await client.cancelQueries({ queryKey: queryKeys.knowledgeBases })
      const previous = client.getQueryData<KnowledgeBase[]>(queryKeys.knowledgeBases)
      client.setQueryData<KnowledgeBase[]>(queryKeys.knowledgeBases, (rows) =>
        (rows ?? []).filter((row) => row.id !== id),
      )
      return { previous }
    },
    onError: (_error, _id, context) => {
      if (context?.previous) {
        client.setQueryData(queryKeys.knowledgeBases, context.previous)
      }
    },
    onSettled: () => {
      client.invalidateQueries({ queryKey: queryKeys.knowledgeBases })
      client.invalidateQueries({ queryKey: queryKeys.conversations })
    },
  })
}

export function useDocuments(kbId: string | null) {
  return useQuery({
    queryKey: queryKeys.documents(kbId ?? ''),
    queryFn: () => apiGet<Document[]>(`/knowledge-bases/${kbId}/documents`),
    enabled: Boolean(kbId),
  })
}

export function useUploadDocument(kbId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => apiUpload<Document>(`/knowledge-bases/${kbId}/documents`, file),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: queryKeys.documents(kbId) })
      client.invalidateQueries({ queryKey: queryKeys.knowledgeBases })
    },
  })
}

export function useDeleteDocument(kbId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (documentId: string) =>
      apiDelete(`/knowledge-bases/${kbId}/documents/${documentId}`),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: queryKeys.documents(kbId) })
      client.invalidateQueries({ queryKey: queryKeys.knowledgeBases })
    },
  })
}

export function useIngestDocument(kbId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (documentId: string) =>
      apiPost<IngestJob>(`/knowledge-bases/${kbId}/documents/${documentId}/ingest`),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: queryKeys.documents(kbId) })
      client.invalidateQueries({ queryKey: queryKeys.knowledgeBases })
    },
  })
}

export function useConversations() {
  return useQuery({
    queryKey: queryKeys.conversations,
    queryFn: () => apiGet<Conversation[]>('/conversations'),
  })
}

export function useCreateConversation() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      knowledge_base_id: string
      pipeline_config_id: string
      title?: string | null
    }) => apiPost<Conversation>('/conversations', body),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.conversations }),
  })
}

export function useDeleteConversation() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiDelete(`/conversations/${id}`),
    onSuccess: (_void, id) => {
      client.invalidateQueries({ queryKey: queryKeys.conversations })
      client.removeQueries({ queryKey: queryKeys.messages(id) })
    },
  })
}

export function useMessages(conversationId: string | null) {
  return useQuery({
    queryKey: queryKeys.messages(conversationId ?? ''),
    queryFn: () => apiGet<ChatMessage[]>(`/conversations/${conversationId}/messages`),
    enabled: Boolean(conversationId),
  })
}

export function useRunSources(conversationId: string | null, ragRunId: string | null) {
  return useQuery({
    queryKey: queryKeys.runSources(conversationId ?? '', ragRunId ?? ''),
    queryFn: () =>
      apiGet<RagRunSources>(`/conversations/${conversationId}/rag-runs/${ragRunId}/sources`),
    enabled: Boolean(conversationId && ragRunId),
  })
}

export function useSendMessage() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({
      conversationId,
      content,
      onMeta,
      onProgress,
      onDelta,
    }: {
      conversationId: string
      content: string
      onMeta?: (meta: ChatStreamMeta) => void
      onProgress?: (event: PipelineProgressEvent) => void
      onDelta?: (text: string) => void
    }) =>
      streamChatMessage(conversationId, content, {
        onMeta,
        onProgress,
        onDelta,
      }),
    onSuccess: (_turn, vars) => {
      client.invalidateQueries({ queryKey: queryKeys.messages(vars.conversationId) })
      client.invalidateQueries({ queryKey: queryKeys.conversations })
      client.invalidateQueries({ queryKey: queryKeys.usageSummary })
      client.invalidateQueries({ queryKey: queryKeys.usageConversations })
    },
  })
}

export function useScenarios() {
  return useQuery({
    queryKey: queryKeys.scenarios,
    queryFn: () => apiGet<Scenario[]>('/scenarios'),
  })
}

export function useScenario(id: string | null) {
  return useQuery({
    queryKey: queryKeys.scenario(id ?? ''),
    queryFn: () => apiGet<ScenarioDetail>(`/scenarios/${id}`),
    enabled: Boolean(id),
  })
}

export function useCreateScenario() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: ScenarioCreate) => apiPost<Scenario>('/scenarios', body),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.scenarios }),
  })
}

export function useUpdateScenario() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: ScenarioUpdate }) =>
      apiPut<Scenario>(`/scenarios/${id}`, body),
    onSuccess: (_data, vars) => {
      client.invalidateQueries({ queryKey: queryKeys.scenarios })
      client.invalidateQueries({ queryKey: queryKeys.scenario(vars.id) })
    },
  })
}

export function useDeleteScenario() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiDelete(`/scenarios/${id}`),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.scenarios }),
  })
}

export function useCreateEvalItem(scenarioId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: EvalItemCreate) =>
      apiPost<EvalItem>(`/scenarios/${scenarioId}/items`, body),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: queryKeys.scenario(scenarioId) })
      client.invalidateQueries({ queryKey: queryKeys.scenarios })
    },
  })
}

export function useImportScenarioItems(scenarioId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ file, replace }: { file: File; replace: boolean }) =>
      apiUploadForm<ScenarioItemsImportResult>(
        `/scenarios/${scenarioId}/items/import-file`,
        file,
        { replace: replace ? 'true' : 'false' },
      ),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: queryKeys.scenario(scenarioId) })
      client.invalidateQueries({ queryKey: queryKeys.scenarios })
    },
  })
}

export function useDeleteEvalItem(scenarioId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (itemId: string) => apiDelete(`/scenarios/${scenarioId}/items/${itemId}`),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: queryKeys.scenario(scenarioId) })
      client.invalidateQueries({ queryKey: queryKeys.scenarios })
    },
  })
}

export function useCreateEvalSpan(scenarioId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ itemId, body }: { itemId: string; body: EvalItemSpanCreate }) =>
      apiPost<EvalItemSpan>(`/scenarios/${scenarioId}/items/${itemId}/spans`, body),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.scenario(scenarioId) }),
  })
}

export function useDeleteEvalSpan(scenarioId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ itemId, spanId }: { itemId: string; spanId: string }) =>
      apiDelete(`/scenarios/${scenarioId}/items/${itemId}/spans/${spanId}`),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.scenario(scenarioId) }),
  })
}

export function useExperiments() {
  return useQuery({
    queryKey: queryKeys.experiments,
    queryFn: () => apiGet<Experiment[]>('/experiments'),
  })
}

export function useExperiment(id: string | null) {
  return useQuery({
    queryKey: queryKeys.experiment(id ?? ''),
    queryFn: () => apiGet<Experiment>(`/experiments/${id}`),
    enabled: Boolean(id),
  })
}

export function useCreateExperiment() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: ExperimentCreate) => apiPost<Experiment>('/experiments', body),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.experiments }),
  })
}

export function useDeleteExperiment() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiDelete(`/experiments/${id}`),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.experiments }),
  })
}

export function useExperimentRuns(experimentId: string | null) {
  return useQuery({
    queryKey: queryKeys.experimentRuns(experimentId ?? ''),
    queryFn: () => apiGet<EvalRun[]>(`/experiments/${experimentId}/runs`),
    enabled: Boolean(experimentId),
    refetchInterval: (query) => {
      const rows = query.state.data
      if (rows?.some((row) => row.status === 'queued' || row.status === 'running')) {
        return 2000
      }
      return false
    },
  })
}

export function useExperimentRun(experimentId: string | null, runId: string | null) {
  return useQuery({
    queryKey: queryKeys.experimentRun(experimentId ?? '', runId ?? ''),
    queryFn: () => apiGet<EvalRunDetail>(`/experiments/${experimentId}/runs/${runId}`),
    enabled: Boolean(experimentId && runId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'queued' || status === 'running' ? 2000 : false
    },
  })
}

export function useStartExperimentRun(experimentId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => apiPost<EvalRunDetail>(`/experiments/${experimentId}/runs`),
    onSuccess: (run) => {
      client.invalidateQueries({ queryKey: queryKeys.experimentRuns(experimentId) })
      client.invalidateQueries({ queryKey: queryKeys.experiment(experimentId) })
      client.invalidateQueries({ queryKey: queryKeys.experiments })
      client.invalidateQueries({ queryKey: queryKeys.usageSummary })
      client.invalidateQueries({ queryKey: queryKeys.usageExperiments })
      client.setQueryData(queryKeys.experimentRun(experimentId, run.id), run)
    },
  })
}

export function usePromoteExperimentRun(experimentId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({
      runId,
      compareVariantId,
    }: {
      runId: string
      compareVariantId?: string | null
    }) =>
      apiPost<Promotion>(`/experiments/${experimentId}/runs/${runId}/promote`, {
        compare_variant_id: compareVariantId ?? null,
      }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: queryKeys.experiment(experimentId) })
      client.invalidateQueries({ queryKey: queryKeys.pipelines })
      client.invalidateQueries({ queryKey: queryKeys.knowledgeBases })
    },
  })
}

export function useUsageSummary() {
  return useQuery({
    queryKey: queryKeys.usageSummary,
    queryFn: () => apiGet<UsageSummary>('/usage/summary'),
  })
}

export function useConversationUsage() {
  return useQuery({
    queryKey: queryKeys.usageConversations,
    queryFn: () => apiGet<ConversationUsage[]>('/usage/conversations'),
  })
}

export function useExperimentUsage() {
  return useQuery({
    queryKey: queryKeys.usageExperiments,
    queryFn: () => apiGet<ExperimentUsage[]>('/usage/experiments'),
  })
}
