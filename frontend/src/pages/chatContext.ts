import i18n from '../i18n'

export function conversationMatchesContext(
  conversation: { knowledge_base_id: string | null; pipeline_config_id: string | null } | null,
  kbId: string | undefined,
  pipelineId: string | null | undefined,
): boolean {
  if (!conversation || !kbId || !conversation.knowledge_base_id) {
    return false
  }
  return (
    conversation.knowledge_base_id === kbId &&
    (conversation.pipeline_config_id ?? null) === (pipelineId ?? null)
  )
}

export function sessionLabel(conversation: {
  id: string
  title: string | null
  updated_at?: string
}): string {
  const title = conversation.title?.trim()
  if (title) {
    return title
  }
  return i18n.t('chat.sessionFallback', { id: conversation.id.slice(0, 8) })
}

export function formatRelativeTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return ''
  }
  const diffMs = Date.now() - date.getTime()
  const minute = 60_000
  const hour = 60 * minute
  const day = 24 * hour
  if (diffMs < minute) {
    return i18n.t('chat.justNow')
  }
  if (diffMs < hour) {
    return i18n.t('chat.minutesAgo', { count: Math.floor(diffMs / minute) })
  }
  if (diffMs < day) {
    return i18n.t('chat.hoursAgo', { count: Math.floor(diffMs / hour) })
  }
  if (diffMs < 7 * day) {
    return i18n.t('chat.daysAgo', { count: Math.floor(diffMs / day) })
  }
  return date.toLocaleDateString(i18n.resolvedLanguage === 'en' ? 'en' : 'zh-CN')
}
