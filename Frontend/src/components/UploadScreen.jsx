import { useState, useRef, useCallback } from 'react'
import { CloudUpload, FileUp, Search, Languages, FileSpreadsheet, AlertCircle, Loader2 } from 'lucide-react'

export default function UploadScreen({ onUpload, uploading, error }) {
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef(null)

  const handleFile = useCallback((file) => {
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      alert('Please upload a PDF file')
      return
    }
    if (file.size > 50 * 1024 * 1024) {
      alert('File too large (max 50 MB)')
      return
    }
    onUpload(file)
  }, [onUpload])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files[0]
    handleFile(file)
  }, [handleFile])

  const handleDragOver = useCallback((e) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback(() => {
    setIsDragging(false)
  }, [])

  const handleBrowse = useCallback(() => {
    fileInputRef.current?.click()
  }, [])

  const handleFileChange = useCallback((e) => {
    handleFile(e.target.files?.[0])
  }, [handleFile])

  return (
    <div className="card p-10">
      {error && (
        <div className="mb-6 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2 text-sm text-red-700">
          <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={`
          max-w-xl mx-auto border-2 border-dashed rounded-xl p-12 text-center transition-colors
          ${isDragging ? 'border-brand bg-brand-pale' : 'border-gray-300 bg-gray-50'}
          ${uploading ? 'opacity-60 pointer-events-none' : ''}
        `}
      >
        <div className="w-14 h-14 mx-auto mb-4 rounded-full bg-white border border-gray-200 flex items-center justify-center">
          {uploading ? (
            <Loader2 className="w-7 h-7 text-brand animate-spin" />
          ) : (
            <CloudUpload className="w-7 h-7 text-gray-400" />
          )}
        </div>

        <div className="text-base font-medium text-gray-900 mb-1">
          {uploading ? 'Uploading...' : 'Drop your annual report here'}
        </div>
        <div className="text-sm text-gray-500 mb-5 leading-relaxed">
          Upload a 10-K, annual report, or financial statements PDF.<br />
          We'll extract share-based compensation data automatically.
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          onChange={handleFileChange}
          className="hidden"
        />
        <button
          onClick={handleBrowse}
          disabled={uploading}
          className="btn btn-primary"
        >
          <FileUp className="w-4 h-4" />
          {uploading ? 'Processing...' : 'Browse files'}
        </button>

        <div className="text-xs text-gray-400 mt-4">
          PDF · Max 50 MB · Up to 500 pages
        </div>
      </div>

      {/* Feature cards */}
      <div className="max-w-xl mx-auto mt-6 grid grid-cols-3 gap-3">
        <FeatureCard
          icon={<Search className="w-5 h-5 text-blue-600" />}
          title="3-stage detection"
          subtitle="Finds the right pages"
        />
        <FeatureCard
          icon={<Languages className="w-5 h-5 text-blue-600" />}
          title="Any disclosure style"
          subtitle="UK · US · Asia"
        />
        <FeatureCard
          icon={<FileSpreadsheet className="w-5 h-5 text-blue-600" />}
          title="Excel export"
          subtitle="7-sheet workbook"
        />
      </div>
    </div>
  )
}

function FeatureCard({ icon, title, subtitle }) {
  return (
    <div className="p-3 bg-gray-50 rounded-lg text-center">
      <div className="flex justify-center mb-1.5">{icon}</div>
      <div className="text-xs font-medium text-gray-900">{title}</div>
      <div className="text-[11px] text-gray-500 mt-0.5">{subtitle}</div>
    </div>
  )
}
