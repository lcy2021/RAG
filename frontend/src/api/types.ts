export type CredentialKind = 'vector' | 'llm'
export type PipelineKind = 'ingest' | 'query'
export type SlotMode = 'first' | 'compare' | 'ensemble'

export type JsonSchema = {
  type?: string
  properties?: Record<string, JsonSchema>
  items?: JsonSchema
  enum?: Array<string | number>
  additionalProperties?: boolean
}

export type HealthResponse = {
  status: string
  version: string
  database: string
}

export type PluginSummary = {
  stage: string
  name: string
  version: string
  description: string
  source: string
  config_schema: JsonSchema
  default_params: Record<string, unknown>
  is_enabled: boolean
}

export type Credential = {
  id: string
  name: string
  kind: CredentialKind
  provider: string
  plugin_name: string
  model_name: string
  base_url: string | null
  key_hint: string | null
  extra: Record<string, unknown>
  created_at: string
  updated_at: string
}

export type CredentialCreate = {
  name: string
  kind: CredentialKind
  model_name: string
  secret: string
  provider?: string
  base_url?: string | null
  extra?: Record<string, unknown>
}

export type CredentialUpdate = {
  name?: string
  kind?: CredentialKind
  model_name?: string
  secret?: string | null
  provider?: string
  base_url?: string | null
  extra?: Record<string, unknown>
}

export type SlotBinding = {
  name: string
  params: Record<string, unknown>
}

export type PipelineSlot = {
  id?: string
  stage: string
  mode: SlotMode
  ordinal: number
  bindings: SlotBinding[]
}

export type Pipeline = {
  id: string
  name: string
  kind: PipelineKind
  description: string | null
  definition: Record<string, unknown>
  slots: PipelineSlot[]
  created_at: string
  updated_at: string
}

export type PipelineCreate = {
  name: string
  kind: PipelineKind
  description?: string | null
  definition?: Record<string, unknown>
  slots: Array<{
    stage: string
    mode: SlotMode
    ordinal?: number
    bindings: SlotBinding[]
  }>
}

export type PipelineUpdate = {
  name: string
  description?: string | null
  definition?: Record<string, unknown>
  slots: Array<{
    stage: string
    mode: SlotMode
    ordinal?: number
    bindings: SlotBinding[]
  }>
}

export type VectorCollection = {
  id: string
  name: string
  embedder_binding_id: string
  metric: string
  dim: number | null
  is_default: boolean
}

export type KnowledgeBase = {
  id: string
  name: string
  description: string | null
  ingest_pipeline_id: string | null
  query_pipeline_id: string | null
  default_embedder_binding_id: string | null
  default_generator_binding_id: string | null
  collections: VectorCollection[]
  created_at: string
  updated_at: string
}

export type KnowledgeBaseCreate = {
  name: string
  description?: string | null
  ingest_pipeline_id: string
}

export type Document = {
  id: string
  knowledge_base_id: string
  source_uri: string
  title: string | null
  status: string
  content_hash: string
  created_at: string
}

export type IngestJob = {
  id: string
  knowledge_base_id: string
  document_id: string | null
  status: string
  error_message: string | null
  stats: Record<string, unknown>
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export type Conversation = {
  id: string
  knowledge_base_id: string | null
  pipeline_config_id: string | null
  title: string | null
  history_window: number
  created_at: string
  updated_at: string
}

export type ChatMessage = {
  id: string
  conversation_id: string
  turn_index: number
  role: string
  content: string
  rag_run_id: string | null
  created_at: string
}

export type StageTrace = {
  stage?: string
  plugin_name?: string
  ordinal?: number
  latency_ms?: number | null
  output?: Record<string, unknown> | null
  error_message?: string | null
  [key: string]: unknown
}

export type RetrievedSource = {
  rank: number
  chunk_id: string | null
  content: string
  score: number | null
  retriever: string
  cited: boolean
}

export type Citation = {
  rank: number
  char_start: number | null
  char_end: number | null
  quote: string | null
}

export type ChatTurn = {
  conversation_id: string
  user: ChatMessage
  assistant: ChatMessage
  rag_run_id: string
  traces: StageTrace[]
  sources: RetrievedSource[]
  citations: Citation[]
}

export type RagRunSources = {
  rag_run_id: string
  sources: RetrievedSource[]
  citations: Citation[]
  traces: StageTrace[]
}

export type ChatStreamMeta = {
  conversation_id: string
  rag_run_id: string
  user: ChatMessage
}

export type PipelineProgressEvent = {
  status: 'running' | 'done' | 'error'
  stage: string
  plugin_name: string
  ordinal: number
  latency_ms?: number | null
  output?: Record<string, unknown> | null
  error_message?: string | null
}

export type EvalItemSpan = {
  id: string
  eval_item_id: string
  document_id: string
  char_start: number | null
  char_end: number | null
  quote: string
}

export type EvalItem = {
  id: string
  dataset_id: string
  question: string
  expected: string | null
  metadata: Record<string, unknown>
  spans: EvalItemSpan[]
}

export type EvalItemCreate = {
  question: string
  expected?: string | null
  metadata?: Record<string, unknown>
}

export type EvalItemSpanCreate = {
  document_id: string
  quote: string
  char_start?: number | null
  char_end?: number | null
}

export type Scenario = {
  id: string
  name: string
  knowledge_base_id: string
  dataset_id: string
  metric_plugins: string[]
  metric_weights: Record<string, number>
  latency_p95_ms_max: number | null
  cost_micros_max: number | null
  notes: string | null
  item_count: number
  created_at: string
}

export type ScenarioDetail = Scenario & {
  items: EvalItem[]
}

export type ScenarioCreate = {
  name: string
  knowledge_base_id: string
  metric_plugins: string[]
  metric_weights?: Record<string, number>
  latency_p95_ms_max?: number | null
  cost_micros_max?: number | null
  notes?: string | null
}

export type ScenarioUpdate = {
  name: string
  metric_plugins: string[]
  metric_weights?: Record<string, number>
  latency_p95_ms_max?: number | null
  cost_micros_max?: number | null
  notes?: string | null
}

export type ScenarioItemsImportResult = {
  created_items: number
  created_spans: number
  replaced: boolean
  warnings: string[]
}

export type SlotOverride = {
  plugin: string
  params?: Record<string, unknown>
}

export type CompareVariantIn = {
  label: string
  query_pipeline_id?: string | null
  vector_collection_id?: string | null
  slot_overrides?: Record<string, SlotOverride>
}

export type ExperimentCreate = {
  name: string
  scenario_id: string
  query_pipeline_id: string
  variants: CompareVariantIn[]
  metric_plugins?: string[] | null
  judge_binding_id?: string | null
  notes?: string | null
}

export type Experiment = {
  id: string
  name: string
  scenario_id: string
  compare_spec_id: string
  judge_binding_id: string | null
  metric_plugins: string[]
  scenario_name: string | null
  compare_spec_name: string | null
  run_count: number
  created_at: string
}

export type EvalSummary = {
  id: string
  eval_run_id: string
  compare_variant_id: string
  metrics: Record<string, number>
  composite_score: number | null
  latency_p50_ms: number | null
  latency_p95_ms: number | null
  cost_micros_avg: number | null
  rank: number | null
  is_winner: boolean
}

export type EvalScore = {
  id: string
  eval_run_id: string
  eval_item_id: string
  compare_variant_id: string
  rag_run_id: string | null
  metric: string
  value: number
  detail: Record<string, unknown>
}

export type EvalVariantProgress = {
  id: string
  label: string
  ordinal: number
  query_pipeline_id: string | null
  query_pipeline_name: string | null
  status: string
  done_items: number
  total_items: number
  error_message: string | null
}

export type EvalRun = {
  id: string
  experiment_id: string
  status: string
  corpus_fingerprint: string | null
  snapshot: Record<string, unknown>
  winner_variant_id: string | null
  error_message: string | null
  created_at: string
  finished_at: string | null
}

export type EvalRunDetail = EvalRun & {
  summaries: EvalSummary[]
  scores: EvalScore[]
  variants: EvalVariantProgress[]
}

export type Promotion = {
  id: string
  scenario_id: string
  eval_run_id: string
  compare_variant_id: string
  knowledge_base_id: string
  ingest_pipeline_id: string | null
  query_pipeline_id: string | null
  vector_collection_id: string | null
  variant_label: string | null
  query_pipeline_name: string | null
  created_at: string
}
