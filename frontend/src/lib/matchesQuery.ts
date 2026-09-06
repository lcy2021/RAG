export function matchesQuery(haystack: Array<string | null | undefined>, query: string): boolean {
  const needle = query.trim().toLowerCase()
  if (!needle) {
    return true
  }
  return haystack.some((item) => (item ?? '').toLowerCase().includes(needle))
}
