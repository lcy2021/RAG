import { apiFetch, parseApiError } from './client'

describe('parseApiError', () => {
  it('reads a string detail', () => {
    expect(parseApiError({ detail: 'pipeline name already exists' }, 409)).toBe(
      'pipeline name already exists',
    )
  })

  it('joins validation details', () => {
    expect(
      parseApiError({ detail: [{ msg: 'field required' }, { msg: 'invalid uuid' }] }, 422),
    ).toBe('field required; invalid uuid')
  })

  it('falls back to status', () => {
    expect(parseApiError(null, 500)).toBe('Request failed (500)')
  })
})

describe('apiFetch', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('returns JSON on success', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        status: 200,
        ok: true,
        text: async () => JSON.stringify({ status: 'ok' }),
      }),
    )
    await expect(apiFetch<{ status: string }>('/health')).resolves.toEqual({ status: 'ok' })
  })

  it('throws ApiError on failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        status: 404,
        ok: false,
        text: async () => JSON.stringify({ detail: 'not found' }),
      }),
    )
    await expect(apiFetch('/missing')).rejects.toThrow('not found')
  })
})

describe('consumeSseBuffer', () => {
  it('parses complete frames and keeps a partial trailer', async () => {
    const { consumeSseBuffer } = await import('./client')
    const first = consumeSseBuffer('event: meta\ndata: {"ok":true}\n\nevent: delta\ndata: {"text":"h')
    expect(first.events).toEqual([{ event: 'meta', data: '{"ok":true}' }])
    expect(first.rest).toBe('event: delta\ndata: {"text":"h')
    const second = consumeSseBuffer(`${first.rest}i"}\n\n`)
    expect(second.events).toEqual([{ event: 'delta', data: '{"text":"hi"}' }])
    expect(second.rest).toBe('')
  })
})
