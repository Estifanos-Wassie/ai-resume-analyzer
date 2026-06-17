import { useState } from 'react'
import './App.css'

function App() {
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [jobDescription, setJobDescription] = useState("")
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [history, setHistory] = useState([])

  function getScoreClass(score) {
    if (score >= 75) return "score-good"
    if (score >= 50) return "score-mid"
    return "score-low"
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError("")
    setResult(null)

    if (!file) {
      setError("Please select a PDF file.")
      return
    }

    const formData = new FormData()
    formData.append("file", file)
    formData.append("job_description", jobDescription)

    setLoading(true)
    try {
      const res = await fetch("http://localhost:8000/analyze", {
        method: "POST",
        body: formData,
      })

      if (!res.ok) {
        const errBody = await res.json()
        throw new Error(errBody.detail || "Something went wrong.")
      }

      const data = await res.json()
      setResult(data)
      setHistory(prev => [{ filename: file.name, ...data }, ...prev])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <h1>AI Resume Analyzer</h1>
      <p className="subtitle">
        Upload your resume and a job description to get instant AI feedback.
      </p>

      <form onSubmit={handleSubmit}>
        <label
          className={`file-drop ${dragging ? "dragging" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragging(false)
            setFile(e.dataTransfer.files[0])
          }}
        >
          <input
            type="file"
            accept=".pdf"
            onChange={(e) => setFile(e.target.files[0])}
            hidden
          />
          {file ? file.name : "Click or drag a PDF here"}
        </label>

        <label>
          <span className="field-label">Job Description</span>
          <textarea
            rows={8}
            value={jobDescription}
            onChange={(e) => setJobDescription(e.target.value)}
            placeholder="Paste the job description here..."
          />
        </label>

        <button type="submit" disabled={loading}>
          {loading ? (
            <>
              <span className="spinner" />
              Analyzing...
            </>
          ) : (
            "Analyze Resume"
          )}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {result && (
        <div className="result">
          <div className={`score-badge ${getScoreClass(result.match_score)}`}>
            <span className="score-number">{result.match_score}%</span>
            <span className="score-caption">Match Score</span>
          </div>

          <div className="result-card">
            <h3>Strengths</h3>
            <ul>
              {result.strengths.map((s, i) => <li key={i}>{s}</li>)}
            </ul>
          </div>

          <div className="result-card">
            <h3>Missing Skills</h3>
            <ul>
              {result.missing_skills.map((s, i) => <li key={i}>{s}</li>)}
            </ul>
          </div>

          <div className="result-card">
            <h3>Suggestions</h3>
            <ul>
              {result.suggestions.map((s, i) => <li key={i}>{s}</li>)}
            </ul>
          </div>
        </div>
      )}

      {history.length > 1 && (
        <div className="history">
          <h3>Previous Analyses</h3>
          {history.slice(1).map((h, i) => (
            <div key={i} className={`history-item ${getScoreClass(h.match_score)}`}>
              <span className="history-filename">{h.filename}</span>
              <span className="history-score">{h.match_score}%</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default App
