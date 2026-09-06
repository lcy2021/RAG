import type { PipelineKind } from './api/types'

export const FORBIDDEN_PARAM_KEYS = new Set(['api_key', 'api-key', 'secret', 'password', 'token'])

export const INGEST_STAGES = ['loader', 'chunker', 'embedder', 'indexer'] as const

export const QUERY_STAGES = [
  'query_transformer',
  'retriever',
  'fusion',
  'reranker',
  'grader',
  'compressor',
  'generator',
] as const

/** Extensions the KB upload control advertises; auto loader still sniffs MIME. */
export const UPLOAD_ACCEPT =
  '.txt,.md,.markdown,.rst,.log,.yml,.yaml,.xml,.json,.csv,.tsv,.html,.htm,.pdf,.docx,.xlsx,.pptx,.png,.jpg,.jpeg,.webp,.tif,.tiff,.bmp'

export const DEFAULT_INGEST_PLUGINS: Record<string, string> = {
  loader: 'auto',
  chunker: 'recursive',
  embedder: 'openai_embedder',
  indexer: 'pgvector',
}

/** Naive query path; skip grader/compressor stubs that raise NotImplementedError. */
export const DEFAULT_QUERY_PLUGINS: Record<string, string> = {
  query_transformer: 'passthrough',
  retriever: 'dense',
  fusion: 'rrf',
  reranker: 'none',
  generator: 'chat',
}

export const VECTOR_STAGES = new Set(['embedder', 'retriever', 'chunker'])

export const LLM_STAGES = new Set([
  'query_transformer',
  'reranker',
  'grader',
  'compressor',
  'generator',
  'evaluator',
])

export const NAV_ITEMS = [
  { key: '/settings' },
  { key: '/plugins' },
  { key: '/pipelines' },
  { key: '/kb' },
  { key: '/scenarios' },
  { key: '/experiments' },
  { key: '/chat' },
] as const

export function stagesForKind(kind: PipelineKind): readonly string[] {
  return kind === 'ingest' ? INGEST_STAGES : QUERY_STAGES
}

export function defaultPluginForStage(kind: PipelineKind, stage: string): string | undefined {
  const map = kind === 'ingest' ? DEFAULT_INGEST_PLUGINS : DEFAULT_QUERY_PLUGINS
  return map[stage]
}

export function credentialKindForStage(stage: string): 'vector' | 'llm' | null {
  if (VECTOR_STAGES.has(stage)) {
    return 'vector'
  }
  if (LLM_STAGES.has(stage)) {
    return 'llm'
  }
  return null
}

export function isForbiddenParamKey(key: string): boolean {
  return FORBIDDEN_PARAM_KEYS.has(key.toLowerCase())
}
