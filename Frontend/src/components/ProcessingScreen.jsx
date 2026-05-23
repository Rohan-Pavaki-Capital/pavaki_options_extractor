import { Check, Loader2, FileText, ShieldCheck, FileSpreadsheet, Search, Brain, Circle } from 'lucide-react'

const STAGE_CONFIG = [
  { key: 'stage1_keywords', label: 'Stage 1 — Keyword Filter', icon: Search },
  { key: 'stage2_classifier', label: 'Stage 2 — LLM Classifier', icon: Brain },
  { key: 'stage3_extraction', label: 'Stage 3 — Sonnet Extraction', icon: FileText },
  { key: 'validation', label: 'Validation & Math Check', icon: ShieldCheck },
  { key: 'excel_generation', label: 'Excel Generation', icon: FileSpreadsheet },
]

export default function ProcessingScreen({ jobStatus, onCancel }) {
  if (!jobStatus) {
    return (
      <div className="card p-12 text-center">
        <Loader2 className="w-8 h-8 text-brand animate-spin mx-auto mb-3" />
        <div className="text-sm text-gray-500">Initializing extraction...</div>
      </div>
    )
  }

  const { filename, file_size, progress, current_stage, stages, elapsed_seconds, estimated_remaining } = jobStatus

  return (
    <div className="card overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 bg-gray-50 flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-white border border-gray-200 flex items-center justify-center">
          <FileText className="w-5 h-5 text-gray-600" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-gray-900 truncate">{filename}</div>
          <div className="text-xs text-gray-500">
            {(file_size / 1024 / 1024).toFixed(1)} MB · Started {new Date(jobStatus.created_at).toLocaleTimeString()}
          </div>
        </div>
        <span className="text-xs px-3 py-1 bg-blue-50 text-blue-700 rounded-md font-medium flex items-center gap-1.5">
          <Loader2 className="w-3 h-3 animate-spin" />
          Processing
        </span>
      </div>

      <div className="p-6">
        {/* Progress bar */}
        <div className="mb-5">
          <div className="flex justify-between items-baseline mb-1.5">
            <span className="text-sm font-medium text-gray-700">Overall progress</span>
            <span className="text-sm text-gray-500">{progress}%</span>
          </div>
          <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-brand-light rounded-full transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        {/* Stages */}
        <div className="space-y-2">
          {STAGE_CONFIG.map((stage) => {
            const stageData = stages[stage.key] || { status: 'pending' }
            return (
              <StageRow
                key={stage.key}
                label={stage.label}
                icon={stage.icon}
                stageData={stageData}
                isCurrent={current_stage === stage.key}
              />
            )
          })}
        </div>

        {/* Footer stats */}
        <div className="mt-5 p-3 bg-gray-50 rounded-lg flex gap-6 text-xs flex-wrap items-center">
          <Stat label="Elapsed" value={`${elapsed_seconds?.toFixed(1)}s`} />
          {estimated_remaining != null && (
            <Stat label="Est. remaining" value={`~${estimated_remaining.toFixed(0)}s`} />
          )}
          <button onClick={onCancel} className="btn ml-auto text-xs">
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}

function StageRow({ label, icon: Icon, stageData, isCurrent }) {
  const status = stageData.status

  const containerClass =
    status === 'completed' ? 'bg-gray-50' :
    isCurrent ? 'bg-blue-50 border border-blue-200' :
    'bg-white opacity-50'

  const iconWrapClass =
    status === 'completed' ? 'bg-green-100' :
    isCurrent ? 'bg-white' :
    'bg-gray-100'

  return (
    <div className={`flex items-center gap-3 px-3.5 py-3 rounded-lg ${containerClass}`}>
      <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 ${iconWrapClass}`}>
        {status === 'completed' ? (
          <Check className="w-4 h-4 text-green-700" />
        ) : isCurrent ? (
          <Loader2 className="w-4 h-4 text-blue-700 animate-spin" />
        ) : (
          <Circle className="w-4 h-4 text-gray-400" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex justify-between items-baseline">
          <span className={`text-sm font-medium ${isCurrent ? 'text-blue-700' : 'text-gray-900'}`}>
            {label}
          </span>
          <span className={`text-xs ${isCurrent ? 'text-blue-700' : 'text-gray-500'}`}>
            {status === 'completed' && stageData.duration != null
              ? `${stageData.duration.toFixed(1)}s`
              : isCurrent ? 'in progress'
              : 'queued'}
          </span>
        </div>
        {stageData.details && (
          <div className={`text-xs mt-0.5 ${isCurrent ? 'text-blue-600' : 'text-gray-500'}`}>
            {stageData.details}
          </div>
        )}
      </div>
    </div>
  )
}

function Stat({ label, value }) {
  return (
    <div>
      <div className="text-gray-500 mb-0.5">{label}</div>
      <div className="font-medium text-gray-900">{value}</div>
    </div>
  )
}
