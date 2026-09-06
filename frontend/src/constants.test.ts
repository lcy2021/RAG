import {
  credentialKindForStage,
  defaultPluginForStage,
  isForbiddenParamKey,
  stagesForKind,
  UPLOAD_ACCEPT,
} from './constants'

test('stage lists match backend runner order', () => {
  expect(stagesForKind('ingest')).toEqual(['loader', 'chunker', 'embedder', 'indexer'])
  expect(stagesForKind('query')[0]).toBe('query_transformer')
  expect(defaultPluginForStage('ingest', 'chunker')).toBe('recursive')
  expect(defaultPluginForStage('query', 'grader')).toBeUndefined()
  expect(defaultPluginForStage('ingest', 'loader')).toBe('auto')
  expect(UPLOAD_ACCEPT).toContain('.pdf')
  expect(UPLOAD_ACCEPT).toContain('.docx')
  expect(UPLOAD_ACCEPT).toContain('.png')
})

test('rejects secret param names', () => {
  expect(isForbiddenParamKey('api_key')).toBe(true)
  expect(isForbiddenParamKey('chunk_size')).toBe(false)
})

test('maps stages to vector or llm credentials', () => {
  expect(credentialKindForStage('embedder')).toBe('vector')
  expect(credentialKindForStage('generator')).toBe('llm')
  expect(credentialKindForStage('fusion')).toBeNull()
})
