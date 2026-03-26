import React, { useCallback, useRef, useState } from 'react'

interface UploadZoneProps {
  onFile: (file: File) => void
  loading?: boolean
}

export function UploadZone({ onFile, loading }: UploadZoneProps) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragging(false)
      const file = e.dataTransfer.files[0]
      if (file) onFile(file)
    },
    [onFile],
  )

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (file) onFile(file)
    },
    [onFile],
  )

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      className={`flex flex-col items-center justify-center gap-3 border-2 border-dashed rounded-xl p-10 cursor-pointer transition-colors select-none
        ${
          dragging
            ? 'border-brand-500 bg-brand-500/10'
            : 'border-gray-600 hover:border-brand-500 hover:bg-gray-800/50'
        }
        ${loading ? 'pointer-events-none opacity-60' : ''}
      `}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.ai"
        className="hidden"
        onChange={handleChange}
      />
      <div className="text-4xl">📄</div>
      {loading ? (
        <p className="text-gray-400 text-sm">Uploading…</p>
      ) : (
        <>
          <p className="text-gray-300 font-medium">Drop a PDF or .ai file here</p>
          <p className="text-gray-500 text-sm">or click to browse</p>
          <p className="text-gray-600 text-xs mt-1">.pdf · .ai supported</p>
        </>
      )}
    </div>
  )
}
