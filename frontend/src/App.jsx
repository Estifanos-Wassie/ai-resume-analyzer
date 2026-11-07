import { useEffect, useRef, useState } from 'react'
import { analyzeUrl, jobCharacterCount, normalizeApiError, retryAfterSeconds, trimText, validateAnalysis, validateFileList, validateJobDescription } from './analysis'
import './App.css'

function getScoreClass(score) {
  if (score >= 75) return 'score-good'
  if (score >= 50) return 'score-mid'
  return 'score-low'
}

function App() {
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [jobDescription, setJobDescription] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [fieldErrors, setFieldErrors] = useState({})
  const [notice, setNotice] = useState('')
  const [history, setHistory] = useState([])
  const [retryUntil, setRetryUntil] = useState(0)
  const [now, setNow] = useState(Date.now)
  const activeRequest = useRef(null)
  const fileInput = useRef(null)
  const descriptionInput = useRef(null)
  const resultHeading = useRef(null)
  const historyId = useRef(0)
  const retrySeconds = Math.max(0, Math.ceil((retryUntil - now) / 1000))

  useEffect(() => () => {
    activeRequest.current?.abort()
    activeRequest.current = null
  }, [])

  useEffect(() => {
    if (!retryUntil) return
    const timer = setInterval(() => {
      const timestamp = Date.now()
      setNow(timestamp)
      if (timestamp >= retryUntil) setRetryUntil(0)
    }, 1000)
    return () => clearInterval(timer)
  }, [retryUntil])

  useEffect(() => {
    if (result) resultHeading.current?.focus()
  }, [result])

  function cancelRequest(message = 'Analysis cancelled in this tab. You can retry manually.') {
    const pending = activeRequest.current
    activeRequest.current = null
    pending?.abort()
    setLoading(false)
    setNotice(pending ? message : '')
  }

  function inputsChanged() {
    cancelRequest('Inputs changed, so the pending analysis was cancelled. Submit again when ready.')
    setResult(null)
    setError('')
  }

  function chooseFiles(files) {
    inputsChanged()
    const message = validateFileList(files)
    setFieldErrors((previous) => ({ ...previous, file: message }))
    setFile(message ? null : files[0])
    if (message && fileInput.current) fileInput.current.value = ''
  }

  function clearSession() {
    cancelRequest()
    setFile(null)
    setJobDescription('')
    setResult(null)
    setHistory([])
    setError('')
    setFieldErrors({})
    setDragging(false)
    setNotice('Session cleared in this tab.')
    fileInput.current.value = ''
    fileInput.current.focus()
  }

  async function handleSubmit(event) {
    event.preventDefault()
    if (activeRequest.current || retryUntil > Date.now()) return
    const errors = {
      file: validateFileList(file ? [file] : []),
      jobDescription: validateJobDescription(jobDescription),
    }
    setFieldErrors(errors)
    setError('')
    if (errors.file || errors.jobDescription) {
      setNotice('Check the highlighted fields before submitting.')
      if (errors.file) fileInput.current.focus()
      else descriptionInput.current.focus()
      return
    }

    let url
    try { url = analyzeUrl() } catch {
      setError('The analysis service address is not configured correctly. Please contact the site owner.')
      return
    }
    const controller = new AbortController()
    activeRequest.current = controller
    const formData = new FormData()
    formData.append('file', file)
    formData.append('job_description', trimText(jobDescription))
    setLoading(true)
    setResult(null)
    setNotice('Analyzing your resume. You can cancel or change your inputs.')
    try {
      const response = await fetch(url, { method: 'POST', body: formData, signal: controller.signal })
      let data
      try { data = await response.json() } catch { data = null }
      if (activeRequest.current !== controller) return
      if (!response.ok) {
        const normalized = normalizeApiError(response.status, data)
        setError(normalized.message)
        setFieldErrors(normalized.fields)
        const seconds = retryAfterSeconds(response.headers.get('Retry-After'))
        if (seconds) {
          const timestamp = Date.now()
          setNow(timestamp)
          setRetryUntil(timestamp + seconds * 1000)
        }
        setNotice('Analysis did not complete. Your inputs are preserved.')
        return
      }
      if (!validateAnalysis(data)) {
        setError('The analysis service returned an invalid response. Your inputs are preserved; you can retry manually.')
        setNotice('No analysis result was accepted.')
        return
      }
      setResult(data)
      const entry = { id: ++historyId.current, filename: file.name, score: data.match_score }
      setHistory((previous) => [entry, ...previous])
      setNotice('Analysis ready. Review your AI-estimated feedback below.')
    } catch {
      if (activeRequest.current === controller) {
        setError('Could not reach the analysis service. Check your connection and try again manually. Your inputs are preserved.')
        setNotice('Analysis did not complete.')
      }
    } finally {
      if (activeRequest.current === controller) {
        activeRequest.current = null
        setLoading(false)
      }
    }
  }

  return (
    <main className="app">
      <h1>AI Resume Analyzer</h1>
      <p className="subtitle">Upload your resume and a job description for AI-estimated feedback.</p>

      <form onSubmit={handleSubmit} noValidate aria-busy={loading}>
        <div>
          <label className="field-label" htmlFor="resume">Resume PDF</label>
          <label className={`file-drop ${dragging ? 'dragging' : ''}`} htmlFor="resume"
            onDragOver={(event) => { event.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault()
              setDragging(false)
              chooseFiles(Array.from(event.dataTransfer.files))
            }}>
            <input ref={fileInput} id="resume" aria-label="Resume PDF" className="visually-hidden" type="file" accept=".pdf,application/pdf"
              aria-invalid={Boolean(fieldErrors.file)} aria-describedby={`resume-help${fieldErrors.file ? ' resume-error' : ''}`}
              onChange={(event) => { if (event.target.files.length) chooseFiles(Array.from(event.target.files)) }} />
            <span>Choose a PDF or drop it here</span>
            <span className="selected-file">{file ? `Selected: ${file.name}` : 'No file selected'}</span>
          </label>
          <p id="resume-help" className="field-help">One PDF, up to 5 MiB and 20 pages. Scanned or image-only PDFs need a text-based replacement; OCR is unsupported.</p>
          {fieldErrors.file && <p id="resume-error" className="field-error" role="alert">{fieldErrors.file}</p>}
        </div>

        <div>
          <label className="field-label" htmlFor="job-description">Job description</label>
          <textarea ref={descriptionInput} id="job-description" rows={8} value={jobDescription}
            aria-invalid={Boolean(fieldErrors.jobDescription)} aria-describedby={`description-help description-count${fieldErrors.jobDescription ? ' description-error' : ''}`}
            onChange={(event) => {
              inputsChanged()
              const text = event.target.value
              setJobDescription(text)
              setFieldErrors((previous) => ({ ...previous, jobDescription: previous.jobDescription || jobCharacterCount(text) > 20_000 ? validateJobDescription(text) : '' }))
            }} placeholder="Paste the job description here..." />
          <p id="description-help" className="field-help">Required, up to 20,000 characters after trimming. Line breaks count as two characters when sent to the API.</p>
          <p id="description-count" className="field-help">{jobCharacterCount(jobDescription).toLocaleString()} / 20,000 characters</p>
          {fieldErrors.jobDescription && <p id="description-error" className="field-error" role="alert">{fieldErrors.jobDescription}</p>}
        </div>

        <p className="privacy-notice">Submitting sends extracted resume text and your job description to Groq for analysis. The score is an AI estimate, not an employer ATS score or hiring prediction.</p>
        <div className="actions">
          <button type="submit" disabled={loading || retrySeconds > 0}>{loading ? <><span className="spinner" aria-hidden="true" />Analyzing…</> : 'Analyze resume'}</button>
          {loading && <button type="button" className="secondary-button" onClick={() => cancelRequest()}>Cancel analysis</button>}
          <button type="button" className="secondary-button" onClick={clearSession}>Clear session</button>
        </div>
        <p className="field-help">Clear session resets this tab only. It does not delete data held by Groq. Cancelling does not guarantee that provider processing stops.</p>
        {retrySeconds > 0 && <p className="retry-notice">The service asked you to wait. Retry manually in {retrySeconds} seconds; no request will be sent automatically.</p>}
      </form>

      <p role="status" aria-live="polite" className="status-message">{notice}</p>
      {error && <p className="error" role="alert">{error}</p>}

      {result && <section className="result" aria-labelledby="feedback-heading">
        <h2 id="feedback-heading" ref={resultHeading} tabIndex={-1}>Your feedback</h2>
        <div className={`score-badge ${getScoreClass(result.match_score)}`}>
          <span className="score-number">{result.match_score}%</span>
          <span className="score-caption">AI-estimated match</span>
        </div>
        {[['strengths', 'Strengths'], ['missing_skills', 'Missing skills'], ['suggestions', 'Suggestions']].map(([key, title]) => <div className="result-card" key={key}>
          <h3>{title}</h3>
          {result[key].length ? <ul>{result[key].map((text, index) => <li key={index}>{text}</li>)}</ul> : <p>No items reported.</p>}
        </div>)}
      </section>}

      {history.length > 0 && <section className="history" aria-labelledby="history-heading">
        <h2 id="history-heading">Session history</h2>
        <p className="field-help">Completed analyses in this tab only. Cleared on reload or with Clear session.</p>
        {history.map((item) => <div key={item.id} className={`history-item ${getScoreClass(item.score)}`}>
          <span className="history-filename">{item.filename}</span>
          <span className="history-score">{item.score}% AI estimate</span>
        </div>)}
      </section>}
    </main>
  )
}

export default App
