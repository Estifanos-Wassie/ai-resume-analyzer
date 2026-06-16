import { useState } from 'react'
import './App.css'

function App() {
  const [file, setFile] = useState(null)
  const [jobDescription, setJobDescription] = useState("")
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

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
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <h1>AI Resume Analyzer</h1>

      <form onSubmit={handleSubmit}>
        <label>
          Resume (PDF)
          <input
            type="file"
            accept=".pdf"
            onChange={(e) => setFile(e.target.files[0])}
          />
        </label>

        <label>
          Job Description
          <textarea
            rows={8}
            value={jobDescription}
            onChange={(e) => setJobDescription(e.target.value)}
            placeholder="Paste the job description here..."
          />
        </label>

        <button type="submit" disabled={loading}>
          {loading ? "Analyzing..." : "Analyze Resume"}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {result && (
        <div className="result">
          <h2>Match Score: {result.match_score}%</h2>

          <h3>Strengths</h3>
          <ul>
            {result.strengths.map((s, i) => <li key={i}>{s}</li>)}
          </ul>

          <h3>Missing Skills</h3>
          <ul>
            {result.missing_skills.map((s, i) => <li key={i}>{s}</li>)}
          </ul>

          <h3>Suggestions</h3>
          <ul>
            {result.suggestions.map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        </div>
      )}
    </div>
  )
}

export default App
