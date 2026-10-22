import { describe, expect, it } from 'vitest'
import { websocketBase } from './websocketUrl'

describe('WebSocket API origin', () => {
  it('keeps a shared HTTPS deployment on the public host', () => {
    expect(websocketBase('/api/v1', 'https://documind.example')).toBe('wss://documind.example/api/v1')
    expect(websocketBase('', 'https://documind.example')).toBe('wss://documind.example/api/v1')
  })
  it('supports a separate API and the local Vite proxy', () => {
    expect(websocketBase('https://api.example/api/v1/', 'https://documind.example')).toBe('wss://api.example/api/v1')
    expect(websocketBase('', 'http://localhost:5173')).toBe('ws://localhost:5173/api/v1')
  })
})
