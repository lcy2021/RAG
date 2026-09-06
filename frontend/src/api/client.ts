import type { ChatStreamMeta, ChatTurn, PipelineProgressEvent } from './types'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''
const API_PREFIX = '/api/v1'

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export function parseApiError(body: unknown, status: number): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail
    if (typeof detail === 'string') {
      return detail
    }
    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          if (item && typeof item === 'object' && 'msg' in item) {
            return String((item as { msg: unknown }).msg)
          }
          return JSON.stringify(item)
        })
        .join('; ')
    }
  }
  return `Request failed (${status})`
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  const isForm = typeof FormData !== 'undefined' && init.body instanceof FormData
  if (!isForm && init.body != null && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const response = await fetch(`${API_BASE}${API_PREFIX}${path}`, { ...init, headers })
  if (response.status === 204) {
    return undefined as T
  }
  const text = await response.text()
  let data: unknown = null
  if (text) {
    try {
      data = JSON.parse(text) as unknown
    } catch {
      data = { detail: text }
    }
  }
  if (!response.ok) {
    throw new ApiError(parseApiError(data, response.status), response.status)
  }
  return data as T
}

export function apiGet<T>(path: string): Promise<T> {
  return apiFetch<T>(path)
}

export function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: 'POST',
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

export function apiPut<T>(path: string, body?: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: 'PUT',
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

export function apiDelete(path: string): Promise<void> {
  return apiFetch<void>(path, { method: 'DELETE' })
}

export function apiUpload<T>(path: string, file: File): Promise<T> {
  const form = new FormData()
  form.append('file', file)
  return apiFetch<T>(path, { method: 'POST', body: form })
}

export function apiUploadForm<T>(
  path: string,
  file: File,
  fields: Record<string, string> = {},
): Promise<T> {
  const form = new FormData()
  form.append('file', file)
  for (const [key, value] of Object.entries(fields)) {
    form.append(key, value)
  }
  return apiFetch<T>(path, { method: 'POST', body: form })
}

export type SseEvent = {
  event: string
  data: string
}

/** Parse complete SSE frames from a text buffer; returns leftover incomplete bytes. */
export function consumeSseBuffer(buffer: string): { events: SseEvent[]; rest: string } {
  const events: SseEvent[] = []
  const parts = buffer.split('\n\n')
  const rest = parts.pop() ?? ''
  for (const part of parts) {
    if (!part.trim()) {
      continue
    }
    let event = 'message'
    const dataLines: string[] = []
    for (const line of part.split('\n')) {
      if (line.startsWith('event:')) {
        event = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trimStart())
      }
    }
    events.push({ event, data: dataLines.join('\n') })
  }
  return { events, rest }
}

export type ChatStreamHandlers = {
  onMeta?: (meta: ChatStreamMeta) => void
  onProgress?: (event: PipelineProgressEvent) => void
  onDelta?: (text: string) => void
  onDone?: (turn: ChatTurn) => void
}

/** POST chat and consume SSE (meta → progress* → delta* → done | error). */
export async function streamChatMessage(
  conversationId: string,
  content: string,
  handlers: ChatStreamHandlers = {},
  signal?: AbortSignal,
): Promise<ChatTurn> {
  const response = await fetch(
    `${API_BASE}${API_PREFIX}/conversations/${conversationId}/messages/stream`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({ content }),
      signal,
    },
  )
  if (!response.ok) {
    const text = await response.text()
    let data: unknown = null
    if (text) {
      try {
        data = JSON.parse(text) as unknown
      } catch {
        data = { detail: text }
      }
    }
    throw new ApiError(parseApiError(data, response.status), response.status)
  }
  if (!response.body) {
    throw new ApiError('Streaming response body is empty', 502)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let completed: ChatTurn | null = null

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }
    buffer += decoder.decode(value, { stream: true })
    const parsed = consumeSseBuffer(buffer)
    buffer = parsed.rest
    for (const frame of parsed.events) {
      let payload: unknown = null
      if (frame.data) {
        try {
          payload = JSON.parse(frame.data) as unknown
        } catch {
          payload = { detail: frame.data }
        }
      }
      if (frame.event === 'meta') {
        handlers.onMeta?.(payload as ChatStreamMeta)
      } else if (frame.event === 'progress') {
        handlers.onProgress?.(payload as PipelineProgressEvent)
      } else if (frame.event === 'delta') {
        const text =
          payload && typeof payload === 'object' && 'text' in payload
            ? String((payload as { text: unknown }).text)
            : ''
        if (text) {
          handlers.onDelta?.(text)
        }
      } else if (frame.event === 'done') {
        completed = payload as ChatTurn
        handlers.onDone?.(completed)
      } else if (frame.event === 'error') {
        const detail =
          payload && typeof payload === 'object' && 'detail' in payload
            ? String((payload as { detail: unknown }).detail)
            : 'Stream failed'
        throw new ApiError(detail, 502)
      }
    }
  }

  if (!completed) {
    throw new ApiError('Stream ended without a done event', 502)
  }
  return completed
}
