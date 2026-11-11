export const MAX_FILE_BYTES = 5 * 1024 * 1024
export const MAX_JOB_CHARACTERS = 20_000

// Python str.strip() whitespace, including characters that JS trim() omits.
// eslint-disable-next-line no-control-regex -- Python also strips these control separators.
const edgeWhitespace = /^[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+|[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+$/g
export const trimText = (text) => text.replace(edgeWhitespace, '')
export const characterCount = (text) => Array.from(text).length
// Browsers serialize multipart text with CRLF line endings; Python counts both.
export const jobCharacterCount = (text) => characterCount(trimText(text).replace(/\r\n|\r|\n/g, '\r\n'))

export function validateFileList(files) {
  if (files.length > 1) return 'Choose or drop exactly one PDF at a time.'
  if (!files.length) return 'Choose a PDF resume.'
  const file = files[0]
  if (!file.name.toLowerCase().endsWith('.pdf')) return 'Choose a PDF file (.pdf).'
  if (!file.size) return 'This file is empty. Choose a text-based PDF.'
  if (file.size > MAX_FILE_BYTES) return 'Choose a PDF no larger than 5 MiB.'
  return ''
}

export function validateJobDescription(text) {
  if (!trimText(text)) return 'Enter a job description, not just spaces.'
  if (jobCharacterCount(text) > MAX_JOB_CHARACTERS) return 'Use no more than 20,000 characters in the job description.'
  return ''
}

export function analyzeUrl(base = import.meta.env.VITE_API_BASE_URL) {
  const normalized = (base ?? '').trim().replace(/\/+$/, '')
  if (!normalized) throw new Error('API configuration is missing')
  const parsed = new URL(normalized)
  if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password || parsed.search || parsed.hash) throw new Error('API configuration is invalid')
  return `${normalized}/analyze`
}

export function validateAnalysis(data) {
  const fields = ['match_score', 'strengths', 'missing_skills', 'suggestions']
  if (!data || typeof data !== 'object' || Array.isArray(data) || Object.keys(data).length !== fields.length || !fields.every((key) => Object.hasOwn(data, key))) return false
  if (!Number.isInteger(data.match_score) || data.match_score < 0 || data.match_score > 100) return false
  return fields.slice(1).every((key) => Array.isArray(data[key]) && data[key].length <= 20 && data[key].every(
    (item) => typeof item === 'string' && characterCount(trimText(item)) >= 1 && characterCount(trimText(item)) <= 1000,
  ))
}

export function retryAfterSeconds(value, now = Date.now()) {
  if (!value || value.length > 128) return 0
  const trimmed = value.trim()
  if (/^\d{1,10}$/.test(trimmed)) return Math.min(Number(trimmed), 3600)
  if (!/^(Mon|Tue|Wed|Thu|Fri|Sat|Sun), \d{2} [A-Z][a-z]{2} \d{4} \d{2}:\d{2}:\d{2} GMT$/.test(trimmed)) return 0
  const date = Date.parse(trimmed)
  return Number.isFinite(date) ? Math.max(0, Math.min(3600, Math.ceil((date - now) / 1000))) : 0
}

const statusMessages = {
  400: 'The resume could not be read. Choose a valid, readable PDF and try again.',
  413: 'The input is too large. Use a PDF up to 5 MiB and 20 pages, with at most 50,000 extracted characters, and a job description up to 20,000 characters.',
  422: 'Check your PDF and job description. Use a text-based, unencrypted PDF and a nonempty description.',
  502: 'The analysis service could not return usable feedback. Your inputs are preserved; you can retry manually.',
  503: 'The analysis service is temporarily unavailable. Your inputs are preserved; please try again later.',
  504: 'The analysis service timed out. Your inputs are preserved; you can retry manually.',
}

// Exact known messages select local copy; arbitrary server text is never rendered.
const fileDetails = new Map([
  ['Only PDF files are accepted.', 'Choose a PDF file (.pdf).'],
  ['Resume file is empty. Upload a readable PDF.', 'This file is empty. Choose a text-based PDF.'],
  ['Resume PDF is corrupt or unreadable. Upload a readable PDF.', 'This PDF could not be read. Choose a readable, text-based replacement.'],
  ['Resume file exceeds 5 MiB.', 'Choose a PDF no larger than 5 MiB.'],
  ['Resume PDF exceeds 20 pages.', 'Choose a PDF with no more than 20 pages.'],
  ['Extracted resume text exceeds 50,000 characters.', 'Choose a resume with no more than 50,000 extracted characters.'],
  ['Encrypted or password-protected PDFs are unsupported. Upload an unencrypted PDF.', 'Choose an unencrypted PDF without password protection.'],
  ['A text-based PDF is required. Blank or image-only PDFs cannot be analyzed because OCR is unsupported.', 'Choose a text-based PDF. Scanned or image-only PDFs are unsupported because OCR is unavailable.'],
])

export function normalizeApiError(status, body) {
  if (status === 413 && body?.detail === 'Resume and job description exceed the local Free-tier token budget. Shorten the resume or job description and try again. No analysis was sent.') {
    return { message: 'The combined resume and job description exceed the local Free-tier token budget. Shorten either input and try again. No analysis was sent; your inputs are preserved.', fields: {} }
  }
  const fields = {}
  const detail = body?.detail
  if ([400, 413, 422].includes(status)) {
    if (typeof detail === 'string' && fileDetails.has(detail)) fields.file = fileDetails.get(detail)
    if (detail === 'Job description exceeds 20,000 characters.') fields.jobDescription = 'Use no more than 20,000 characters in the job description.'
    if (detail === 'A nonempty job description is required.') fields.jobDescription = 'Enter a job description, not just spaces.'
    if (Array.isArray(detail)) {
      for (const issue of detail) {
        const name = Array.isArray(issue?.loc) ? issue.loc.at(-1) : null
        if (name === 'file') fields.file = 'Choose a valid PDF resume.'
        if (name === 'job_description') fields.jobDescription = 'Enter a valid job description of no more than 20,000 characters.'
      }
    }
  }
  return { message: statusMessages[status] ?? 'The request could not be completed. Your inputs are preserved; try again later.', fields }
}
