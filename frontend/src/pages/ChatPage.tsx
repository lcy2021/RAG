import { DeleteOutlined, PlusOutlined, SendOutlined } from '@ant-design/icons'
import { useQueryClient } from '@tanstack/react-query'
import { Button, Collapse, Empty, Popconfirm, Select, Spin, Tabs, Tag, Typography } from 'antd'
import { Fragment, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import {
  queryKeys,
  useConversations,
  useCreateConversation,
  useDeleteConversation,
  useKnowledgeBases,
  useMessages,
  usePipelines,
  useRunSources,
  useSendMessage,
} from '../api/hooks'
import type {
  ChatMessage,
  Conversation,
  PipelineProgressEvent,
  RetrievedSource,
  StageTrace,
} from '../api/types'
import { useMessage } from '../hooks/useMessage'
import { conversationMatchesContext, formatRelativeTime, sessionLabel } from './chatContext'
import './ChatPage.css'

type StreamDraft = {
  user: ChatMessage
  assistantContent: string
  ragRunId: string | null
}

type ProgressEntry = {
  id: string
  status: 'running' | 'done' | 'error'
  stage: string
  plugin_name: string
  ordinal?: number
  latency_ms?: number | null
  output?: Record<string, unknown> | null
  error_message?: string | null
}

const CITE_SPLIT_RE = /(\[\d+\])/g
const CITE_MARK_RE = /^\[(\d+)\]$/

export function ChatPage() {
  const { t } = useTranslation()
  const message = useMessage()
  const queryClient = useQueryClient()
  const kbs = useKnowledgeBases()
  const pipelines = usePipelines()
  const conversations = useConversations()
  const create = useCreateConversation()
  const removeConversation = useDeleteConversation()
  const send = useSendMessage()
  const [kbId, setKbId] = useState<string>()
  const [pipelineId, setPipelineId] = useState<string | undefined>()
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [conversation, setConversation] = useState<Conversation | null>(null)
  const [draft, setDraft] = useState('')
  const [tracesByRun, setTracesByRun] = useState<Record<string, StageTrace[]>>({})
  const [sourcesByRun, setSourcesByRun] = useState<Record<string, RetrievedSource[]>>({})
  const [streamDraft, setStreamDraft] = useState<StreamDraft | null>(null)
  const [progressLog, setProgressLog] = useState<ProgressEntry[]>([])
  const listRef = useRef<HTMLDivElement>(null)
  const progressSeq = useRef(0)
  const messages = useMessages(conversationId)

  const kbList = kbs.data
  const resolvedKbId = kbId ?? kbList?.[0]?.id
  const selectedKb = kbList?.find((item) => item.id === resolvedKbId)
  const pipelineOptions = useMemo(
    () =>
      (pipelines.data ?? [])
        .filter((item) => item.kind === 'query')
        .map((item) => ({ value: item.id, label: item.name })),
    [pipelines.data],
  )
  const resolvedPipelineId = pipelineId ?? pipelineOptions[0]?.value
  const canReuse = conversationMatchesContext(conversation, resolvedKbId, resolvedPipelineId)
  const stored = messages.data ?? []
  const busy = create.isPending || send.isPending
  const sessions = conversations.data ?? []

  const transcript = useMemo(() => {
    if (!streamDraft) {
      return stored
    }
    const hasUser = stored.some((item) => item.id === streamDraft.user.id)
    const rows = hasUser ? [...stored] : [...stored, streamDraft.user]
    rows.push({
      id: '__streaming_assistant__',
      conversation_id: streamDraft.user.conversation_id,
      turn_index: streamDraft.user.turn_index,
      role: 'assistant',
      content: streamDraft.assistantContent,
      rag_run_id: streamDraft.ragRunId,
      created_at: new Date().toISOString(),
    })
    return rows
  }, [stored, streamDraft])

  const kbOptions = useMemo(
    () => (kbList ?? []).map((item) => ({ value: item.id, label: item.name })),
    [kbList],
  )

  const scrollToBottom = () => {
    requestAnimationFrame(() => {
      const node = listRef.current
      if (node) {
        node.scrollTop = node.scrollHeight
      }
    })
  }

  const openSession = (session: Conversation) => {
    setConversation(session)
    setConversationId(session.id)
    setKbId(session.knowledge_base_id ?? undefined)
    setPipelineId(session.pipeline_config_id ?? undefined)
    setTracesByRun({})
    setSourcesByRun({})
    setStreamDraft(null)
    setProgressLog([])
  }

  const resetThread = () => {
    setConversationId(null)
    setConversation(null)
    setTracesByRun({})
    setSourcesByRun({})
    setStreamDraft(null)
    setProgressLog([])
  }

  const deleteSession = async (session: Conversation) => {
    try {
      await removeConversation.mutateAsync(session.id)
      if (conversationId === session.id) {
        resetThread()
      }
      message.success(t('common.deleted'))
    } catch (error) {
      message.error(error instanceof Error ? error.message : t('common.deleteFailed'))
    }
  }

  const appendProgress = (event: PipelineProgressEvent) => {
    progressSeq.current += 1
    const id = `${progressSeq.current}-${event.stage}-${event.plugin_name}-${event.status}`
    setProgressLog((current) => {
      if (event.status === 'running') {
        return [...current, { ...event, id }]
      }
      const index = [...current]
        .reverse()
        .findIndex(
          (item) =>
            item.status === 'running' &&
            item.stage === event.stage &&
            item.plugin_name === event.plugin_name &&
            item.ordinal === event.ordinal,
        )
      if (index < 0) {
        return [...current, { ...event, id }]
      }
      const realIndex = current.length - 1 - index
      const next = [...current]
      next[realIndex] = { ...event, id }
      return next
    })
    scrollToBottom()
  }

  const submit = async () => {
    const content = draft.trim()
    if (!content || busy) {
      return
    }
    if (!resolvedKbId) {
      message.warning(t('chat.pickKbFirst'))
      return
    }
    if (!resolvedPipelineId) {
      message.warning(t('chat.pickPipelineFirst'))
      return
    }
    try {
      let active = canReuse ? conversation : null
      if (!active) {
        active = await create.mutateAsync({
          knowledge_base_id: resolvedKbId,
          pipeline_config_id: resolvedPipelineId,
          title: content.slice(0, 40),
        })
        setConversation(active)
        setConversationId(active.id)
        setTracesByRun({})
        setSourcesByRun({})
      }
      const pendingUser: ChatMessage = {
        id: '__pending_user__',
        conversation_id: active.id,
        turn_index: -1,
        role: 'user',
        content,
        rag_run_id: null,
        created_at: new Date().toISOString(),
      }
      setDraft('')
      setProgressLog([])
      setStreamDraft({ user: pendingUser, assistantContent: '', ragRunId: null })
      scrollToBottom()

      const turn = await send.mutateAsync({
        conversationId: active.id,
        content,
        onMeta: (meta) => {
          setStreamDraft((current) =>
            current
              ? { ...current, user: meta.user, ragRunId: meta.rag_run_id }
              : {
                  user: meta.user,
                  assistantContent: '',
                  ragRunId: meta.rag_run_id,
                },
          )
          scrollToBottom()
        },
        onProgress: appendProgress,
        onDelta: (text) => {
          setStreamDraft((current) =>
            current ? { ...current, assistantContent: current.assistantContent + text } : current,
          )
          scrollToBottom()
        },
      })
      setTracesByRun((current) => ({ ...current, [turn.rag_run_id]: turn.traces }))
      setSourcesByRun((current) => ({ ...current, [turn.rag_run_id]: turn.sources ?? [] }))
      await queryClient.invalidateQueries({ queryKey: queryKeys.messages(active.id) })
      setStreamDraft(null)
      setProgressLog([])
      scrollToBottom()
    } catch (error) {
      setStreamDraft(null)
      if (conversationId) {
        await queryClient.invalidateQueries({ queryKey: queryKeys.messages(conversationId) })
      }
      message.error(error instanceof Error ? error.message : t('chat.sendFailed'))
    }
  }

  const showEmpty = transcript.length === 0 && !streamDraft

  return (
    <div className="chat-page">
      <aside className="chat-session-rail">
        <div className="chat-session-rail-header">
          <Typography.Text strong>{t('chat.history')}</Typography.Text>
          <Button type="link" size="small" icon={<PlusOutlined />} onClick={resetThread}>
            {t('chat.newChat')}
          </Button>
        </div>
        <div className="chat-session-rail-list">
          {conversations.isLoading ? (
            <div className="chat-session-rail-empty">
              <Spin size="small" />
            </div>
          ) : sessions.length === 0 ? (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={t('chat.noSessions')} />
          ) : (
            sessions.map((item) => {
              const active = item.id === conversationId
              const kbName = kbList?.find((kb) => kb.id === item.knowledge_base_id)?.name
              return (
                <div
                  key={item.id}
                  className={`chat-session-item${active ? ' is-active' : ''}`}
                >
                  <button
                    type="button"
                    className="chat-session-item-main"
                    onClick={() => openSession(item)}
                  >
                    <span className="chat-session-item-title">{sessionLabel(item)}</span>
                    <span className="chat-session-item-meta">
                      {kbName ?? t('chat.kbFallback')}
                      {item.updated_at ? ` · ${formatRelativeTime(item.updated_at)}` : ''}
                    </span>
                  </button>
                  <Popconfirm
                    title={t('chat.deleteSessionConfirm')}
                    okText={t('common.delete')}
                    okButtonProps={{ danger: true }}
                    onConfirm={(event) => {
                      event?.stopPropagation()
                      void deleteSession(item)
                    }}
                    onCancel={(event) => event?.stopPropagation()}
                  >
                    <Button
                      type="text"
                      size="small"
                      danger
                      className="chat-session-item-delete"
                      icon={<DeleteOutlined />}
                      aria-label={t('chat.deleteSession')}
                      loading={removeConversation.isPending && removeConversation.variables === item.id}
                      onClick={(event) => event.stopPropagation()}
                    />
                  </Popconfirm>
                </div>
              )
            })
          )}
        </div>
      </aside>

      <div className="chat-shell">
        <div className="chat-transcript" ref={listRef}>
          {showEmpty ? (
            <div className="chat-empty">
              <Typography.Title level={3} style={{ marginBottom: 8 }}>
                {t('chat.askTitle')}
              </Typography.Title>
              <Typography.Text type="secondary">{t('chat.askHint')}</Typography.Text>
            </div>
          ) : (
            transcript.map((item) => (
              <ChatBubble
                key={item.id}
                message={item}
                conversationId={conversationId}
                streaming={item.id === '__streaming_assistant__'}
                progress={item.id === '__streaming_assistant__' ? progressLog : undefined}
                traces={item.rag_run_id ? tracesByRun[item.rag_run_id] : undefined}
                cachedSources={item.rag_run_id ? sourcesByRun[item.rag_run_id] : undefined}
              />
            ))
          )}
        </div>

        <div className="chat-composer">
          <div className="chat-composer-toolbar">
            <label className="chat-composer-field">
              <span className="chat-composer-field-label">{t('chat.kbPlaceholder')}</span>
              <Select
                size="small"
                variant="borderless"
                placeholder={t('chat.kbPlaceholder')}
                value={resolvedKbId}
                options={kbOptions}
                popupMatchSelectWidth={false}
                style={{ minWidth: 120, maxWidth: 220 }}
                onChange={(value) => {
                  setKbId(value)
                  resetThread()
                }}
              />
            </label>
            <label className="chat-composer-field">
              <span className="chat-composer-field-label">{t('chat.pipelinePlaceholder')}</span>
              <Select
                size="small"
                variant="borderless"
                placeholder={t('chat.pipelinePlaceholder')}
                value={resolvedPipelineId}
                options={pipelineOptions}
                popupMatchSelectWidth={false}
                style={{ minWidth: 140, maxWidth: 260 }}
                onChange={(value) => {
                  setPipelineId(value)
                  resetThread()
                }}
              />
            </label>
          </div>
          <textarea
            className="chat-composer-input"
            value={draft}
            placeholder={t('chat.inputPlaceholder')}
            rows={3}
            disabled={busy}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                void submit()
              }
            }}
          />
          <div className="chat-composer-actions">
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {selectedKb ? t('chat.currentKb', { name: selectedKb.name }) : t('chat.noKb')}
            </Typography.Text>
            <Button type="primary" icon={<SendOutlined />} loading={busy} onClick={() => void submit()}>
              {t('common.send')}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

function tracesToProgress(traces: StageTrace[], runKey: string): ProgressEntry[] {
  return traces.map((trace, index) => ({
    id: `${runKey}-trace-${index}-${String(trace.stage)}-${String(trace.plugin_name)}`,
    status: trace.error_message ? 'error' : 'done',
    stage: String(trace.stage ?? ''),
    plugin_name: String(trace.plugin_name ?? ''),
    ordinal: typeof trace.ordinal === 'number' ? trace.ordinal : index,
    latency_ms: trace.latency_ms,
    output: trace.output ?? null,
    error_message: trace.error_message ? String(trace.error_message) : null,
  }))
}

type StagePassage = {
  rank: number
  content: string
  chunk_id?: string
  score?: number
  rerank_score?: number
  grade?: number
}

function asPassages(value: unknown): StagePassage[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object')
    .map((item, index) => ({
      rank: typeof item.rank === 'number' ? item.rank : index + 1,
      content: typeof item.content === 'string' ? item.content : '',
      chunk_id: item.chunk_id != null ? String(item.chunk_id) : undefined,
      score: typeof item.score === 'number' ? item.score : undefined,
      rerank_score: typeof item.rerank_score === 'number' ? item.rerank_score : undefined,
      grade: typeof item.grade === 'number' ? item.grade : undefined,
    }))
}

function formatScore(value: number | undefined, label: string): string | null {
  if (value == null || Number.isNaN(value)) {
    return null
  }
  return `${label} ${value.toFixed(3)}`
}

function PassageResultList({
  passages,
  dimmedBelow,
}: {
  passages: StagePassage[]
  dimmedBelow?: number
}) {
  const { t } = useTranslation()
  if (passages.length === 0) {
    return (
      <Typography.Text type="secondary" className="chat-stage-empty">
        {t('chat.stageNoPassages')}
      </Typography.Text>
    )
  }
  return (
    <div className="chat-stage-passages">
      <Typography.Text type="secondary" className="chat-stage-passage-count">
        {t('chat.stagePassageCount', { count: passages.length })}
      </Typography.Text>
      {passages.map((passage) => {
        const dimmed = dimmedBelow != null && (passage.grade ?? 1) < dimmedBelow
        const scores = [
          formatScore(passage.score, 'score'),
          formatScore(passage.rerank_score, 'rerank'),
          formatScore(passage.grade, 'grade'),
        ].filter(Boolean)
        return (
          <div
            key={`${passage.rank}-${passage.chunk_id ?? passage.content.slice(0, 24)}`}
            className={`chat-source${dimmed ? ' is-dimmed' : ''}`}
          >
            <div className="chat-source-head">
              <Typography.Text code>[{passage.rank}]</Typography.Text>
              {scores.map((label) => (
                <Typography.Text key={label!} type="secondary" style={{ fontSize: 12 }}>
                  {label}
                </Typography.Text>
              ))}
            </div>
            <Typography.Paragraph
              className="chat-source-body"
              ellipsis={{ rows: 6, expandable: true, symbol: t('chat.expandPassage') }}
            >
              {passage.content || t('common.none')}
            </Typography.Paragraph>
          </div>
        )
      })}
    </div>
  )
}

function StageTypedResult({ stage, output }: { stage: string; output: Record<string, unknown> }) {
  const { t } = useTranslation()
  const passages = asPassages(output.passages)
  const byPlugin =
    output.passages_by_plugin && typeof output.passages_by_plugin === 'object'
      ? (output.passages_by_plugin as Record<string, unknown>)
      : null

  if (stage === 'query_transformer') {
    const hypos = Array.isArray(output.hypothetical_docs)
      ? output.hypothetical_docs.map(String)
      : []
    const queries = Array.isArray(output.search_queries)
      ? output.search_queries.map(String)
      : []
    return (
      <div className="chat-stage-typed">
        {output.query != null ? (
          <div className="chat-stage-kv">
            <span className="chat-stage-k">{t('chat.stageOriginalQuery')}</span>
            <span className="chat-stage-v">{String(output.query)}</span>
          </div>
        ) : null}
        {output.rewritten_query != null ? (
          <div className="chat-stage-kv">
            <span className="chat-stage-k">{t('chat.stageRewrittenQuery')}</span>
            <span className="chat-stage-v">{String(output.rewritten_query)}</span>
          </div>
        ) : null}
        {queries.length > 0 ? (
          <div className="chat-stage-list-block">
            <Typography.Text type="secondary">{t('chat.stageSearchQueries')}</Typography.Text>
            {queries.map((item, index) => (
              <Typography.Paragraph key={`${index}-${item.slice(0, 16)}`} className="chat-stage-list-item">
                {item}
              </Typography.Paragraph>
            ))}
          </div>
        ) : null}
        {hypos.length > 0 ? (
          <div className="chat-stage-list-block">
            <Typography.Text type="secondary">{t('chat.stageHypotheticalDocs')}</Typography.Text>
            {hypos.map((item, index) => (
              <Typography.Paragraph
                key={`${index}-${item.slice(0, 16)}`}
                className="chat-stage-list-item"
                ellipsis={{ rows: 4, expandable: true }}
              >
                {item}
              </Typography.Paragraph>
            ))}
          </div>
        ) : null}
      </div>
    )
  }

  if (stage === 'retriever' && byPlugin && Object.keys(byPlugin).length > 0) {
    const pluginNames = Object.keys(byPlugin)
    const items = [
      {
        key: 'merged',
        label: t('chat.stageMerged'),
        children: <PassageResultList passages={passages} />,
      },
      ...pluginNames.map((name) => ({
        key: name,
        label: `${name} (${asPassages(byPlugin[name]).length})`,
        children: <PassageResultList passages={asPassages(byPlugin[name])} />,
      })),
    ]
    return <Tabs size="small" items={items} className="chat-stage-tabs" />
  }

  if (
    stage === 'retriever' ||
    stage === 'fusion' ||
    stage === 'reranker' ||
    stage === 'compressor' ||
    stage === 'grader'
  ) {
    return (
      <div className="chat-stage-typed">
        {stage === 'grader' ? (
          <div className="chat-stage-kv">
            <span className="chat-stage-k">{t('chat.stageCragAction')}</span>
            <span className="chat-stage-v">
              {String(output.crag_action ?? t('common.none'))}
              {typeof output.crag_max_score === 'number'
                ? ` · max ${output.crag_max_score.toFixed(3)}`
                : ''}
            </span>
          </div>
        ) : null}
        <PassageResultList
          passages={passages}
          dimmedBelow={stage === 'grader' ? 0.5 : undefined}
        />
      </div>
    )
  }

  if (stage === 'generator') {
    const marks = Array.isArray(output.citation_marks)
      ? output.citation_marks.map(String)
      : []
    return (
      <Typography.Text type="secondary">
        {marks.length > 0
          ? t('chat.stageGeneratorDoneCited', { marks: marks.join(' ') })
          : t('chat.stageGeneratorDone')}
      </Typography.Text>
    )
  }

  const leftover = { ...output }
  delete leftover.passages
  delete leftover.passages_by_plugin
  if (Object.keys(leftover).length === 0) {
    return (
      <Typography.Text type="secondary" className="chat-stage-empty">
        {t('chat.stageSummaryOnly')}
      </Typography.Text>
    )
  }
  return <pre className="chat-progress-output">{JSON.stringify(leftover, null, 2)}</pre>
}

function stageSummaryLine(item: ProgressEntry, t: (key: string, opts?: Record<string, unknown>) => string) {
  const output = item.output
  if (!output) {
    return null
  }
  if (typeof output.retrieved_count === 'number') {
    return t('chat.stageCountLine', { count: output.retrieved_count })
  }
  if (output.rewritten_query != null) {
    return String(output.rewritten_query).slice(0, 48)
  }
  if (Array.isArray(output.citation_marks) && output.citation_marks.length > 0) {
    return output.citation_marks.map(String).join(' ')
  }
  return null
}

function PipelineProgressPanel({
  entries,
  live = false,
}: {
  entries: ProgressEntry[]
  live?: boolean
}) {
  const { t } = useTranslation()
  const bodyRef = useRef<HTMLDivElement>(null)
  const cardRefs = useRef<Record<string, HTMLDivElement | null>>({})
  const hasRunning = entries.some((item) => item.status === 'running')
  const [pinnedExpanded, setPinnedExpanded] = useState<boolean | null>(null)
  const expanded = pinnedExpanded ?? (live && hasRunning)
  const focusId =
    entries.find((item) => item.status === 'error')?.id ??
    entries.find((item) => item.status === 'running')?.id ??
    entries[entries.length - 1]?.id ??
    null
  const [pinnedOpenId, setPinnedOpenId] = useState<string | null | undefined>(undefined)
  const openId = pinnedOpenId !== undefined ? pinnedOpenId : focusId

  // Only auto-scroll inside the panel during live streaming — never scroll the chat transcript.
  useEffect(() => {
    if (!live || !expanded || !openId) {
      return
    }
    const body = bodyRef.current
    const node = cardRefs.current[openId]
    if (!body || !node) {
      return
    }
    const bodyRect = body.getBoundingClientRect()
    const nodeRect = node.getBoundingClientRect()
    const above = nodeRect.top < bodyRect.top
    const below = nodeRect.bottom > bodyRect.bottom
    if (above || below) {
      body.scrollTo({
        top: body.scrollTop + (nodeRect.top - bodyRect.top) - 8,
        behavior: 'smooth',
      })
    }
  }, [live, openId, expanded, hasRunning, entries.length])

  if (entries.length === 0) {
    return null
  }

  const totalMs = entries.reduce((sum, item) => sum + (item.latency_ms ?? 0), 0)
  const failed = entries.some((item) => item.status === 'error')
  const current =
    entries.find((item) => item.status === 'running') ?? entries[entries.length - 1]
  const summaryLabel = hasRunning
    ? t('chat.progressRunning', {
        stage: current?.stage ?? '',
        plugin: current?.plugin_name ?? '',
      })
    : failed
      ? t('chat.progressFailedSummary', { count: entries.length, ms: totalMs })
      : t('chat.progressDoneSummary', { count: entries.length, ms: totalMs })

  return (
    <div
      className={`chat-progress${expanded ? ' is-expanded' : ' is-collapsed'}${live && hasRunning ? ' is-live' : ''}`}
    >
      <div className="chat-progress-bar">
        <div className="chat-progress-bar-text">
          <span className="chat-progress-title">{t('chat.progressTitle')}</span>
          <Typography.Text type="secondary" className="chat-progress-summary">
            {summaryLabel}
          </Typography.Text>
        </div>
        <Button
          type="link"
          size="small"
          className="chat-progress-toggle"
          onClick={() => setPinnedExpanded(!expanded)}
        >
          {expanded ? t('chat.progressCollapse') : t('chat.progressExpand')}
        </Button>
      </div>

      <div className="chat-progress-timeline" aria-hidden={!expanded}>
        {entries.map((item, index) => (
          <Fragment key={`tl-${item.id}`}>
            {index > 0 ? <span className="chat-progress-timeline-sep">→</span> : null}
            <button
              type="button"
              className={`chat-progress-step is-${item.status}${openId === item.id ? ' is-active' : ''}`}
              onClick={() => {
                setPinnedExpanded(true)
                setPinnedOpenId(item.id)
              }}
              title={`${item.stage} / ${item.plugin_name}`}
            >
              <span className="chat-progress-step-dot" />
              <span className="chat-progress-step-label">
                {t(`stages.${item.stage}`, { defaultValue: item.stage })}
              </span>
              {item.latency_ms != null ? (
                <span className="chat-progress-step-ms">{item.latency_ms}ms</span>
              ) : null}
            </button>
          </Fragment>
        ))}
      </div>

      {expanded ? (
        <div className="chat-progress-body" ref={bodyRef}>
          {entries.map((item) => {
            const open = openId === item.id
            const summary = stageSummaryLine(item, t)
            return (
              <div
                key={item.id}
                ref={(node) => {
                  cardRefs.current[item.id] = node
                }}
                className={`chat-progress-item is-${item.status}${open ? ' is-open' : ''}`}
              >
                <button
                  type="button"
                  className="chat-progress-item-toggle"
                  onClick={() => setPinnedOpenId(open ? null : item.id)}
                >
                  <div className="chat-progress-head">
                    <Tag
                      color={
                        item.status === 'running'
                          ? 'processing'
                          : item.status === 'error'
                            ? 'error'
                            : 'success'
                      }
                    >
                      {t(`chat.progressStatus.${item.status}`)}
                    </Tag>
                    <Typography.Text>
                      {t(`stages.${item.stage}`, { defaultValue: item.stage })} · {item.plugin_name}
                    </Typography.Text>
                    {item.latency_ms != null ? (
                      <Typography.Text type="secondary" className="chat-progress-latency">
                        {item.latency_ms}ms
                      </Typography.Text>
                    ) : null}
                    {summary ? (
                      <Typography.Text type="secondary" className="chat-progress-item-summary">
                        {summary}
                      </Typography.Text>
                    ) : null}
                  </div>
                </button>
                {open ? (
                  <div className="chat-progress-item-body">
                    {item.error_message ? (
                      <Typography.Text type="danger" className="chat-progress-error">
                        {item.error_message}
                      </Typography.Text>
                    ) : null}
                    {item.output ? (
                      <StageTypedResult stage={item.stage} output={item.output} />
                    ) : item.status === 'running' ? (
                      <Typography.Text type="secondary">{t('chat.progressStatus.running')}</Typography.Text>
                    ) : (
                      <Typography.Text type="secondary" className="chat-stage-empty">
                        {t('chat.stageSummaryOnly')}
                      </Typography.Text>
                    )}
                  </div>
                ) : null}
              </div>
            )
          })}
        </div>
      ) : null}
    </div>
  )
}

function ChatBubble({
  message,
  conversationId,
  traces,
  cachedSources,
  progress,
  streaming = false,
}: {
  message: ChatMessage
  conversationId: string | null
  traces?: StageTrace[]
  cachedSources?: RetrievedSource[]
  progress?: ProgressEntry[]
  streaming?: boolean
}) {
  const { t } = useTranslation()
  const isUser = message.role === 'user'
  // Keep a stable key while streaming (rag_run_id arrives mid-turn); isolate by run once persisted.
  const runKey = streaming ? message.id : (message.rag_run_id ?? message.id)
  const needsFetch =
    !isUser && !streaming && Boolean(message.rag_run_id) && !(cachedSources && traces)
  const remote = useRunSources(
    needsFetch ? conversationId : null,
    needsFetch ? message.rag_run_id : null,
  )
  const sources = cachedSources ?? remote.data?.sources ?? []
  const progressEntries = useMemo(() => {
    if (progress && progress.length > 0) {
      return progress
    }
    if (streaming) {
      return []
    }
    const resolved = traces ?? remote.data?.traces ?? []
    if (resolved.length === 0) {
      return []
    }
    return tracesToProgress(resolved, runKey)
  }, [progress, streaming, traces, remote.data?.traces, runKey])

  const collapseItems = []
  if (!isUser && !streaming && sources.length > 0) {
    collapseItems.push({
      key: 'sources',
      label: t('chat.sourcesCount', { count: sources.length }),
      children: (
        <div className="chat-sources">
          {sources.map((source) => (
            <div
              key={`${source.rank}-${source.chunk_id ?? 'x'}`}
              id={`source-${message.rag_run_id}-${source.rank}`}
              className={`chat-source${source.cited ? ' is-cited' : ''}`}
            >
              <div className="chat-source-head">
                <Typography.Text code>[{source.rank}]</Typography.Text>
                {source.cited ? <Tag color="blue">{t('chat.cited')}</Tag> : null}
                {source.score != null ? (
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    {source.score.toFixed(3)}
                  </Typography.Text>
                ) : null}
              </div>
              <Typography.Paragraph className="chat-source-body" ellipsis={{ rows: 4, expandable: true }}>
                {source.content}
              </Typography.Paragraph>
            </div>
          ))}
        </div>
      ),
    })
  }

  return (
    <div className={`chat-bubble-row ${isUser ? 'is-user' : 'is-assistant'}`}>
      <div className="chat-bubble">
        <div className="chat-bubble-role">{isUser ? t('chat.you') : t('chat.assistant')}</div>
        {!isUser ? (
          <PipelineProgressPanel key={runKey} entries={progressEntries} live={streaming} />
        ) : null}
        <div className={`chat-bubble-body${streaming ? ' is-streaming' : ''}`}>
          {isUser || streaming
            ? message.content
            : renderAnswerWithCitations(message.content, message.rag_run_id)}
          {streaming ? <span className="chat-stream-caret" aria-hidden /> : null}
        </div>
        {collapseItems.length > 0 ? <Collapse size="small" ghost items={collapseItems} /> : null}
      </div>
    </div>
  )
}

function renderAnswerWithCitations(content: string, ragRunId: string | null): ReactNode {
  const parts = content.split(CITE_SPLIT_RE)
  return parts.map((part, index) => {
    const match = part.match(CITE_MARK_RE)
    if (!match) {
      return <Fragment key={`t-${index}`}>{part}</Fragment>
    }
    const rank = match[1]
    const target = ragRunId ? `#source-${ragRunId}-${rank}` : undefined
    return (
      <a key={`c-${index}`} className="chat-cite" href={target}>
        [{rank}]
      </a>
    )
  })
}
