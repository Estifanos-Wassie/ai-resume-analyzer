import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach, vi } from 'vitest'

beforeEach(() => {
  vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000///')
  vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('Network forbidden in unit tests'))))
})
afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
  vi.useRealTimers()
})
