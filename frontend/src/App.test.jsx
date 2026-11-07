import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import App from './App'

const valid = { match_score: 75, strengths: ['Synthetic Python experience'], missing_skills: ['SQL'], suggestions: [] }
const pdf = () => new File(['synthetic PDF bytes'], 'synthetic.PDF', { type: 'application/pdf' })
const reply = (data = valid, status = 200, headers = {}) => ({ ok: status >= 200 && status < 300, status, headers: new Headers(headers), json: async () => data })
const deferred = () => {
  let resolve
  const promise = new Promise((done) => { resolve = done })
  return { promise, resolve }
}
async function prepare() {
  const user = userEvent.setup()
  const view = render(<App />)
  await user.upload(screen.getByLabelText('Resume PDF', { exact: true }), pdf())
  fireEvent.change(screen.getByLabelText('Job description'), { target: { value: '  Python developer  ' } })
  return { user, ...view }
}
const submit = () => fireEvent.submit(screen.getByRole('button', { name: 'Analyze resume' }).closest('form'))

it('shows field errors and focuses an accessible file input without requesting', async () => {
  const user = userEvent.setup()
  render(<App />)
  await user.click(screen.getByRole('button', { name: 'Analyze resume' }))
  expect(screen.getByText('Choose a PDF resume.')).toBeVisible()
  expect(screen.getByText('Enter a job description, not just spaces.')).toBeVisible()
  expect(screen.getByLabelText('Resume PDF', { exact: true })).toHaveFocus()
  expect(fetch).not.toHaveBeenCalled()
})

it('applies equivalent validation to picker and multiple-file drops', () => {
  render(<App />)
  const picker = screen.getByLabelText('Resume PDF', { exact: true })
  fireEvent.change(picker, { target: { files: [new File(['bad'], 'bad.docx')] } })
  expect(screen.getByRole('alert')).toHaveTextContent('(.pdf)')
  fireEvent.drop(picker.closest('.file-drop'), { dataTransfer: { files: [pdf(), pdf()] } })
  expect(screen.getByRole('alert')).toHaveTextContent('exactly one')
  expect(fetch).not.toHaveBeenCalled()
})

it('submits trimmed multipart input once, renders feedback, and clears all session state', async () => {
  fetch.mockResolvedValue(reply())
  const { user } = await prepare()
  submit()
  await screen.findByRole('heading', { name: 'Your feedback' })
  const [url, options] = fetch.mock.calls[0]
  expect(url).toBe('http://localhost:8000/analyze')
  expect(options.body.get('job_description')).toBe('Python developer')
  expect(options.body.get('file').name).toBe('synthetic.PDF')
  expect(screen.getByText('AI-estimated match')).toBeVisible()
  expect(screen.getByRole('heading', { name: 'Session history' })).toBeVisible()
  await user.click(screen.getByRole('button', { name: 'Clear session' }))
  expect(screen.getByLabelText('Job description')).toHaveValue('')
  expect(screen.getByLabelText('Resume PDF', { exact: true }).value).toBe('')
  expect(screen.getByText('No file selected')).toBeVisible()
  expect(screen.queryByRole('heading', { name: 'Your feedback' })).not.toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Session history' })).not.toBeInTheDocument()
  expect(screen.getByRole('status')).toHaveTextContent('Session cleared')
})

it('prevents duplicate submissions even before the pending render completes', async () => {
  const pending = deferred()
  fetch.mockReturnValue(pending.promise)
  await prepare()
  act(() => { submit(); submit() })
  expect(fetch).toHaveBeenCalledTimes(1)
  expect(screen.getByRole('button', { name: 'Analyzing…' })).toBeDisabled()
  await act(async () => pending.resolve(reply()))
})

it('ignores late responses after changed input and a newer request', async () => {
  const old = deferred()
  const newer = deferred()
  fetch.mockReturnValueOnce(old.promise).mockReturnValueOnce(newer.promise)
  await prepare()
  submit()
  const firstSignal = fetch.mock.calls[0][1].signal
  fireEvent.change(screen.getByLabelText('Job description'), { target: { value: 'New job description' } })
  expect(firstSignal.aborted).toBe(true)
  submit()
  await act(async () => newer.resolve(reply({ ...valid, match_score: 90 })))
  await screen.findByText('90%')
  await act(async () => old.resolve(reply({ ...valid, match_score: 10 })))
  expect(screen.queryByText('10%')).not.toBeInTheDocument()
  expect(screen.getByText('90%')).toBeVisible()
})

it('clears stale results immediately when inputs change', async () => {
  fetch.mockResolvedValue(reply())
  await prepare()
  submit()
  await screen.findByRole('heading', { name: 'Your feedback' })
  fireEvent.change(screen.getByLabelText('Job description'), { target: { value: 'Different job' } })
  expect(screen.queryByRole('heading', { name: 'Your feedback' })).not.toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Session history' })).toBeVisible()
})

it.each(['cancel', 'clear', 'unmount'])('aborts on %s and ignores responses that ignore abort', async (action) => {
  const pending = deferred()
  fetch.mockReturnValue(pending.promise)
  const { user, unmount } = await prepare()
  submit()
  const signal = fetch.mock.calls[0][1].signal
  if (action === 'unmount') unmount()
  else await user.click(screen.getByRole('button', { name: action === 'cancel' ? 'Cancel analysis' : 'Clear session' }))
  expect(signal.aborted).toBe(true)
  await act(async () => pending.resolve(reply()))
  expect(screen.queryByRole('heading', { name: 'Your feedback' })).not.toBeInTheDocument()
})

it.each([400, 413, 422, 502, 503, 504])('handles HTTP %i safely and permits a successful manual retry', async (status) => {
  fetch.mockResolvedValueOnce(reply({ detail: 'SENSITIVE_SERVER_EXCEPTION' }, status)).mockResolvedValueOnce(reply())
  await prepare()
  submit()
  expect(await screen.findByRole('alert')).not.toHaveTextContent('SENSITIVE')
  expect(screen.getByLabelText('Job description')).toHaveValue('  Python developer  ')
  expect(fetch).toHaveBeenCalledTimes(1)
  submit()
  await screen.findByRole('heading', { name: 'Your feedback' })
  expect(fetch).toHaveBeenCalledTimes(2)
})

it('handles non-JSON and schema-invalid success without crashing or inventing results', async () => {
  fetch.mockResolvedValueOnce({ ...reply(), json: async () => { throw new Error('SENSITIVE_RAW_BODY') } }).mockResolvedValueOnce(reply({ match_score: '75' }))
  await prepare()
  for (let index = 0; index < 2; index++) {
    submit()
    expect(await screen.findByRole('alert')).toHaveTextContent('invalid response')
    expect(screen.getByRole('alert')).not.toHaveTextContent('SENSITIVE')
    expect(screen.queryByRole('heading', { name: 'Your feedback' })).not.toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole('button', { name: 'Analyze resume' })).toBeEnabled())
  }
})

it('handles a network failure without exposing its exception or retrying automatically', async () => {
  fetch.mockRejectedValue(new Error('SENSITIVE_NETWORK_EXCEPTION'))
  await prepare()
  submit()
  expect(await screen.findByRole('alert')).toHaveTextContent('Check your connection')
  expect(screen.getByRole('alert')).not.toHaveTextContent('SENSITIVE')
  expect(fetch).toHaveBeenCalledTimes(1)
})

it('honors Retry-After across session clearing and enables only a manual retry', async () => {
  fetch.mockResolvedValue(reply({ detail: 'rate limited' }, 503, { 'Retry-After': '10' }))
  await prepare()
  vi.useFakeTimers()
  await act(async () => submit())
  expect(screen.getByText(/Retry manually in 10 seconds/)).toBeVisible()
  expect(screen.getByRole('button', { name: 'Analyze resume' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Clear session' }))
  expect(screen.getByRole('button', { name: 'Analyze resume' })).toBeDisabled()
  await act(async () => { await vi.advanceTimersByTimeAsync(10_000) })
  expect(screen.getByRole('button', { name: 'Analyze resume' })).toBeEnabled()
  expect(fetch).toHaveBeenCalledTimes(1)
})
