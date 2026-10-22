/** Resolve HTTP and WebSocket traffic against the same configured API origin. */
export function websocketBase(apiUrl: string, origin: string): string {
  const url = new URL(apiUrl || '/api/v1', origin)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  url.search = ''
  url.hash = ''
  return url.toString().replace(/\/$/, '')
}
