import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { renderWithI18n } from '../test/i18n'
import { SchemaForm, decodeStringTag, encodeStringTag } from './SchemaForm'

const schema = {
  type: 'object',
  properties: {
    chunk_size: { type: 'integer' },
    api_key: { type: 'string' },
    metric: { type: 'string', enum: ['cosine', 'l2'] },
  },
}

test('renders schema fields and hides forbidden keys', async () => {
  const user = userEvent.setup()
  const onChange = vi.fn()
  renderWithI18n(<SchemaForm schema={schema} value={{}} onChange={onChange} />)

  expect(screen.getByText('chunk_size')).toBeInTheDocument()
  expect(screen.getByText('metric')).toBeInTheDocument()
  expect(screen.queryByText('api_key')).not.toBeInTheDocument()

  await user.click(screen.getByRole('spinbutton'))
  await user.keyboard('512')
  expect(onChange).toHaveBeenCalled()
})

test('shows empty hint when plugin has no params', async () => {
  renderWithI18n(
    <SchemaForm
      schema={{ type: 'object', additionalProperties: false }}
      value={{}}
      onChange={() => undefined}
    />,
    'en',
  )
  expect(
    await screen.findByText(/This plugin needs no params/i),
  ).toBeInTheDocument()
})

test('encodes separators for tag display', () => {
  expect(encodeStringTag('\n\n')).toBe('\\n\\n')
  expect(encodeStringTag('')).toBe('(empty)')
  expect(decodeStringTag('\\n\\n')).toBe('\n\n')
  expect(decodeStringTag('(empty)')).toBe('')
})