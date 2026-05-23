import { useState, useEffect, useCallback } from 'react'
import { BarChart3 } from 'lucide-react'
import UploadScreen from './components/UploadScreen'
import ProcessingScreen from './components/ProcessingScreen'
import ResultsScreen from './components/ResultsScreen'

const API_BASE = `${import.meta.env.VITE_API_BASE || ''}/api`

export default function App() {
  // State machine: 'idle' | 'uploading' | 'processing' | 'completed' | 'failed'
  const [screen, setScreen] = useState('idle')
  const [jobId, setJobId] = useState(null)
  const [jobStatus, setJobStatus] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  // Poll job status every 1s while processing
  useEffect(() => {
    if (!jobId || screen !== 'processing') return

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/job/${jobId}`)
        if (!res.ok) throw new Error('Failed to fetch job status')
        const data = await res.json()
        setJobStatus(data)

        if (data.status === 'completed') {
          // Fetch the final result
          const resultRes = await fetch(`${API_BASE}/result/${jobId}`)
          if (resultRes.ok) {
            const resultData = await resultRes.json()
            setResult(resultData)
            setScreen('completed')
          }
        } else if (data.status === 'failed') {
          setError(data.error || 'Extraction failed')
          setScreen('failed')
        }
      } catch (err) {
        console.error('Polling error:', err)
      }
    }, 1000)

    return () => clearInterval(interval)
  }, [jobId, screen])

  const handleUpload = useCallback(async (file) => {
    setError(null)
    setScreen('uploading')

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch(`${API_BASE}/extract`, {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || `Upload failed (${res.status})`)
      }

      const data = await res.json()
      setJobId(data.job_id)
      setScreen('processing')
    } catch (err) {
      setError(err.message)
      setScreen('failed')
    }
  }, [])

  const handleReset = useCallback(() => {
    setScreen('idle')
    setJobId(null)
    setJobStatus(null)
    setResult(null)
    setError(null)
  }, [])

  const handleCancel = useCallback(async () => {
    if (!jobId) return
    try {
      await fetch(`${API_BASE}/job/${jobId}`, { method: 'DELETE' })
    } catch (err) {
      console.error('Cancel failed:', err)
    }
    handleReset()
  }, [jobId, handleReset])

  return (
    <div className="min-h-screen bg-gray-50">
      {/* App Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-brand flex items-center justify-center">
              <BarChart3 className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="font-medium text-[15px] text-gray-900">
                Pavaki Options Extractor
              </div>
              <div className="text-xs text-gray-500">
                Extract share-based payment data from annual reports
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500"></span>
              API ready
            </span>
            {screen !== 'idle' && (
              <button onClick={handleReset} className="btn text-xs">
                New extraction
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-6xl mx-auto px-6 py-8">
        {(screen === 'idle' || screen === 'uploading' || screen === 'failed') && (
          <UploadScreen
            onUpload={handleUpload}
            uploading={screen === 'uploading'}
            error={error}
          />
        )}

        {screen === 'processing' && (
          <ProcessingScreen
            jobStatus={jobStatus}
            onCancel={handleCancel}
          />
        )}

        {screen === 'completed' && result && (
          <ResultsScreen
            result={result}
            jobId={jobId}
            apiBase={API_BASE}
            onReset={handleReset}
          />
        )}
      </main>

      <footer className="max-w-6xl mx-auto px-6 py-6 text-center text-xs text-gray-400 border-t border-gray-100 mt-12">
        Pavaki Options Extractor · 3-stage extraction pipeline · Claude Sonnet 4
      </footer>
    </div>
  )
}
