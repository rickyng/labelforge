import { useCallback, useRef, useState } from 'react'

interface JsonUploadZoneProps {
  onFile: (file: File) => void
  loading?: boolean
  result?: { source_file: string; style_id: string; sizes: string[] } | null
}

export function JsonUploadZone({ onFile, loading, result }: JsonUploadZoneProps) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file && file.name.endsWith('.json')) onFile(file)
  }, [onFile])

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) onFile(file)
  }, [onFile])

  return (
    <div className="space-y-2">
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => !loading && inputRef.current?.click()}
        className={`flex flex-col items-center justify-center gap-2 border-2 border-dashed rounded-xl p-6 cursor-pointer transition-colors select-none
          ${dragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-blue-500 hover:bg-blue-50/60'}
          ${loading ? 'pointer-events-none opacity-60' : ''}`}
      >
        <input ref={inputRef} type="file" accept=".json" className="hidden" onChange={handleChange} />
        {loading ? (
          <span className="text-sm text-gray-500">Processing...</span>
        ) : result ? (
          <span className="text-sm text-green-600 font-medium">{result.source_file} &mdash; {result.sizes.length} sizes</span>
        ) : (
          <span className="text-sm text-gray-400">Drop order JSON here or click to browse</span>
        )}
      </div>
      {result && (
        <div className="text-xs text-gray-500">
          Style: <span className="font-medium">{result.style_id}</span> &middot; Sizes: {result.sizes.join(', ')}
        </div>
      )}
    </div>
  )
}
