/** Download helpers and CSV/JSON templates for scenario gold-set import. */

/** UTF-8 BOM so Excel on Windows opens Chinese CSV correctly. */
const UTF8_BOM = '\uFEFF'

function downloadBlob(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

export function downloadScenarioCsvTemplate(): void {
  const content = [
    'question,expected,document,quote',
    '"公司成立于哪一年？","2019年","handbook.md","本公司成立于2019年。"',
    '"公司成立于哪一年？","","handbook.md","总部设在上海。"',
    '"默认向量维度是多少？","1536","faq.md","默认 embedding 维度为 1536。"',
    '',
  ].join('\n')
  downloadBlob(
    'scenario-items-template.csv',
    UTF8_BOM + content,
    'text/csv;charset=utf-8',
  )
}

export function downloadScenarioJsonTemplate(): void {
  const payload = {
    items: [
      {
        question: '公司成立于哪一年？',
        expected: '2019年',
        spans: [
          { document: 'handbook.md', quote: '本公司成立于2019年。' },
          { document: 'handbook.md', quote: '总部设在上海。' },
        ],
      },
      {
        question: '默认向量维度是多少？',
        expected: '1536',
        spans: [{ document: 'faq.md', quote: '默认 embedding 维度为 1536。' }],
      },
    ],
  }
  downloadBlob(
    'scenario-items-template.json',
    `${JSON.stringify(payload, null, 2)}\n`,
    'application/json;charset=utf-8',
  )
}
