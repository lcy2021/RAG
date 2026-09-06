import '../i18n'
import i18n from '../i18n'
import { conversationMatchesContext, sessionLabel } from './chatContext'

beforeEach(async () => {
  await i18n.changeLanguage('zh')
})

test('requires the same knowledge base and query pipeline', () => {
  const conversation = {
    knowledge_base_id: 'kb-1',
    pipeline_config_id: 'pipe-1',
  }
  expect(conversationMatchesContext(conversation, 'kb-1', 'pipe-1')).toBe(true)
  expect(conversationMatchesContext(conversation, 'kb-2', 'pipe-1')).toBe(false)
  expect(conversationMatchesContext(conversation, 'kb-1', null)).toBe(false)
  expect(conversationMatchesContext(null, 'kb-1', 'pipe-1')).toBe(false)
})

test('sessionLabel prefers title then short id', async () => {
  expect(sessionLabel({ id: 'abcdef12-xxxx', title: '  切块问题  ' })).toBe('切块问题')
  expect(sessionLabel({ id: 'abcdef12-xxxx', title: null })).toBe('会话 abcdef12')
  await i18n.changeLanguage('en')
  expect(sessionLabel({ id: 'abcdef12-xxxx', title: null })).toBe('Chat abcdef12')
})
