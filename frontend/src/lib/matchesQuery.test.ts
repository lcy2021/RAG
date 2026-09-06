import { describe, expect, it } from 'vitest'

import { matchesQuery } from './matchesQuery'

describe('matchesQuery', () => {
  it('matches any haystack field case-insensitively', () => {
    expect(matchesQuery(['Naive RAG', 'ingest'], 'rag')).toBe(true)
    expect(matchesQuery(['Naive RAG'], 'xyz')).toBe(false)
  })

  it('treats empty query as match-all', () => {
    expect(matchesQuery([''], '  ')).toBe(true)
  })
})
