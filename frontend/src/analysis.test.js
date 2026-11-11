import { describe, expect, it } from 'vitest'
import { analyzeUrl, characterCount, jobCharacterCount, MAX_FILE_BYTES, normalizeApiError, retryAfterSeconds, trimText, validateAnalysis, validateFileList, validateJobDescription } from './analysis'

const valid = { match_score: 75, strengths: ['Python'], missing_skills: [], suggestions: ['Add evidence'] }
const file = (name = 'resume.PDF', size = 100) => ({ name, size })

describe('input and configuration contract', () => {
  it.each([
    [[], 'Choose a PDF'], [[file(), file()], 'exactly one'], [[file('a.docx')], '(.pdf)'],
    [[file('a.pdf', 0)], 'empty'], [[file('a.pdf', MAX_FILE_BYTES + 1)], '5 MiB'],
  ])('rejects invalid file selection %j', (files, message) => expect(validateFileList(files)).toContain(message))
  it('accepts uppercase PDF extensions and the exact byte limit without trusting MIME', () => {
    expect(validateFileList([file('resume.PDF', MAX_FILE_BYTES)])).toBe('')
  })
  it('uses Python whitespace and Unicode code points, including multipart CRLF', () => {
    expect(trimText('\u0085\u001c 😀 \u001f')).toBe('😀')
    expect(trimText('\ufeff')).toBe('\ufeff')
    expect(characterCount('😀')).toBe(1)
    expect(jobCharacterCount('  😀\nPython  ')).toBe(9)
    expect(jobCharacterCount('a\r\nb')).toBe(4)
    expect(validateJobDescription('😀'.repeat(20_000))).toBe('')
    expect(validateJobDescription('😀'.repeat(20_001))).toContain('20,000')
    expect(validateJobDescription('\u0085 \n\t ')).toContain('not just spaces')
  })
  it('enforces the serialized job description boundary', () => {
    expect(validateJobDescription('x'.repeat(19_997) + '\ny')).toBe('')
    expect(validateJobDescription('x'.repeat(19_998) + '\ny')).toContain('20,000')
  })
  it('normalizes the configured URL and refuses absent or credentialed addresses', () => {
    expect(analyzeUrl(' https://api.example/prefix/// ')).toBe('https://api.example/prefix/analyze')
    expect(analyzeUrl()).toBe('http://localhost:8000/analyze')
    for (const value of ['', 'broken', 'ftp://api.example', 'https://key:secret@api.example', 'https://api.example?token=secret']) expect(() => analyzeUrl(value)).toThrow()
  })
})

describe('response validation', () => {
  it('accepts the public schema, boundary scores, empty arrays, and Unicode feedback', () => {
    expect(validateAnalysis(valid)).toBe(true)
    expect(validateAnalysis({ ...valid, match_score: 0, strengths: [] })).toBe(true)
    expect(validateAnalysis({ ...valid, match_score: 100, strengths: ['😀'.repeat(1000)] })).toBe(true)
  })
  it.each([true, false, '75', 75.5, -1, 101, null, NaN, Infinity])('rejects score %j', (match_score) => expect(validateAnalysis({ ...valid, match_score })).toBe(false))
  it.each([null, [], {}, 'raw response', { ...valid, strengths: undefined }, { ...valid, extra: 'secret' }])('rejects malformed structure %j', (value) => expect(validateAnalysis(value)).toBe(false))
  it.each(['strengths', 'missing_skills', 'suggestions'])('requires valid %s arrays', (field) => {
    for (const value of [undefined, null, '', {}, [true], [7], [''], [' \u0085 '], ['x'.repeat(1001)], Array(21).fill('x')]) expect(validateAnalysis({ ...valid, [field]: value })).toBe(false)
  })
})

describe('safe errors and manual retry', () => {
  it('asks users to shorten combined input for the known local token-budget error', () => {
    const detail = 'Resume and job description exceed the local Free-tier token budget. Shorten the resume or job description and try again. No analysis was sent.'
    const result = normalizeApiError(413, { detail })
    expect(result.message).toContain('Shorten either input')
    expect(result.message).toContain('No analysis was sent')
    expect(result.message).toContain('inputs are preserved')
    expect(normalizeApiError(413, { detail: `${detail} SECRET` }).message).not.toContain('SECRET')
  })
  it.each([400, 413, 422, 502, 503, 504, 500])('normalizes HTTP %i without echoing raw details', (status) => {
    const result = normalizeApiError(status, { detail: 'SENSITIVE_SERVER_TRACE' })
    expect(result.message).toBeTruthy()
    expect(JSON.stringify(result)).not.toContain('SENSITIVE')
  })
  it('normalizes known string and FastAPI validation-array errors to local field messages', () => {
    expect(normalizeApiError(413, { detail: 'Resume PDF exceeds 20 pages.' }).fields.file).toContain('20 pages')
    const result = normalizeApiError(422, { detail: [{ loc: ['body', 'file'], msg: 'SECRET', input: 'SECRET' }, { loc: ['body', 'job_description'], msg: 'SECRET' }] })
    expect(result.fields.file).toContain('PDF')
    expect(result.fields.jobDescription).toContain('description')
    expect(JSON.stringify(result)).not.toContain('SECRET')
    expect(normalizeApiError(503, null).message).toContain('temporarily unavailable')
  })
  it('accepts only safe retry delays and dates, bounded to an hour', () => {
    expect(retryAfterSeconds('12')).toBe(12)
    expect(retryAfterSeconds('999999')).toBe(3600)
    expect(retryAfterSeconds('Sat, 07 Nov 2026 00:00:45 GMT', Date.UTC(2026, 10, 7))).toBe(45)
    for (const value of [null, 'raw-secret', '-1', '1.5', 'Bad\r\nHeader:secret']) {
      expect(retryAfterSeconds(value)).toBe(0)
    }
  })
})
