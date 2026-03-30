import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { applyProfile, downloadUrl, listConfigs, loadConfig,
         logout, outputPreviewUrl, previewUrl } from '../api'
import { PdfViewer } from '../components/PdfViewer'
import { ZoomControls } from '../components/ZoomControls'
import { useToast } from '../components/Toast'
import { UserHighlightOverlay } from '../components/UserHighlightOverlay'
import { ResizablePanel } from '../components/ResizablePanel'
import { getRole } from '../utils/auth'
import type { ConfigSummary, FieldEntry, Label, ProfileApplyResponse } from '../types'

export default function User() {
  const navigate = useNavigate()
  const { addToast } = useToast()

  const [profiles, setProfiles] = useState<ConfigSummary[]>([])
  const [selectedProfile, setSelectedProfile] = useState('')
  const [sessionId, setSessionId] = useState('')
  const [pageCount, setPageCount] = useState(1)
  const [currentPage, setCurrentPage] = useState(0)
  const [availableSizes, setAvailableSizes] = useState<string[]>([])
  const [selectedSize, setSelectedSize] = useState('')
  const [fieldsBySize, setFieldsBySize] = useState<Record<string, FieldEntry[]>>({})
  const [applyResult, setApplyResult] = useState<ProfileApplyResponse | null>(null)
  const [loadingProfile, setLoadingProfile] = useState(false)
  const [applying, setApplying] = useState(false)
  const [applyError, setApplyError] = useState<string | null>(null)
  const [zoom, setZoom] = useState(1)
  const [profileLabels, setProfileLabels] = useState<Label[]>([])
  const [canvasDims, setCanvasDims] = useState<{ w: number; h: number; scale: number } | null>(null)
  const [hoveredLabelId, setHoveredLabelId] = useState<string | null>(null)
  const handleDimensions = useCallback((w: number, h: number, scale: number) => {
    setCanvasDims({ w, h, scale })
  }, [])

  useEffect(() => {
    if (getRole() !== 'user') navigate('/login')
  }, [navigate])

  useEffect(() => {
    listConfigs().then(all => setProfiles(all.filter(p => p.has_changes)))
  }, [])

  const handleSelectProfile = useCallback(async (profileName: string) => {
    setSelectedProfile(profileName)
    if (!profileName) return
    setLoadingProfile(true)
    try {
      const data = await loadConfig(profileName)
      setSessionId(data.session_id)
      setPageCount(data.page_count)
      setCurrentPage(0)
      setProfileLabels(data.labels as unknown as Label[])
      const rawSizes: any[] = (data as any).changes_data?.sizes ?? []
      const sizes = rawSizes.map((s: any) => s.size_name)
      setAvailableSizes(sizes)
      setSelectedSize(sizes[0] ?? '')
      const fbs: Record<string, FieldEntry[]> = {}
      rawSizes.forEach((s: any) => { fbs[s.size_name] = s.fields ?? [] })
      setFieldsBySize(fbs)
      setApplyResult(null)
    } catch (e: any) {
      addToast(e.message, 'error')
    } finally {
      setLoadingProfile(false)
    }
  }, [addToast])

  useEffect(() => {
    if (!selectedProfile || !selectedSize) return
    setApplying(true)
    setApplyError(null)
    applyProfile(selectedProfile, selectedSize)
      .then(result => {
        setApplyResult(result)
        setCurrentPage(0)
        if (result.warning) {
          addToast(result.warning!, 'warning')
        }
      })
      .catch((e: any) => {
        setApplyError(e.message)
        addToast(e.message, 'error')
      })
      .finally(() => setApplying(false))
  }, [selectedProfile, selectedSize])

  const highlightedIds = useMemo(() => {
    if (!selectedSize) return new Set<string>()
    const fields = fieldsBySize[selectedSize] ?? []
    return new Set(fields.map(f => f.label_id).filter(Boolean))
  }, [selectedSize, fieldsBySize])

  const previewSrc = applyResult
    ? outputPreviewUrl(applyResult.session_id)
    : sessionId
      ? previewUrl(sessionId)
      : ''


  return (
    <div className="h-screen overflow-hidden flex flex-col">
      <header className="flex items-center justify-between px-4 py-2 border-b bg-white">
        <span className="font-semibold text-sm">LabelForge — User</span>
        <button onClick={() => logout().then(() => navigate('/login'))}
          className="text-xs text-gray-500 hover:text-gray-800">Logout</button>
      </header>
      <div className="flex flex-1 overflow-hidden">
        <ResizablePanel defaultWidth={256} minWidth={160} maxWidth={480} className="border-r bg-gray-50 flex flex-col gap-4 p-4 overflow-y-auto">
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase mb-1">Profile</p>
            <select
              className="w-full border rounded px-2 py-1 text-sm"
              value={selectedProfile}
              onChange={e => handleSelectProfile(e.target.value)}
              disabled={loadingProfile}
            >
              <option value="">Select a profile...</option>
              {profiles.map(p => (
                <option key={p.name} value={p.name}>{p.name}</option>
              ))}
            </select>
          </div>
          {availableSizes.length > 0 && (
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase mb-1">Size</p>
              <select
                className="w-full border rounded px-2 py-1 text-sm"
                value={selectedSize}
                onChange={e => setSelectedSize(e.target.value)}
              >
                {availableSizes.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          )}
          {selectedSize && fieldsBySize[selectedSize]?.length > 0 && (
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase mb-1">Fields</p>
              <div className="overflow-x-auto">
                <table className="w-full text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-gray-200 text-gray-400">
                      <th className="py-1 pr-2 text-left">#</th>
                      <th className="py-1 pr-2 text-left">Field</th>
                      <th className="py-1 pr-2 text-left">Value</th>
                      <th className="py-1 text-left">Component ID</th>
                    </tr>
                  </thead>
                  <tbody>
                    {fieldsBySize[selectedSize].map(f => (
                      <tr
                        key={f.num}
                        className={`border-b border-gray-100 cursor-default ${
                          f.label_id && hoveredLabelId === f.label_id ? 'bg-amber-50' : ''
                        }`}
                        onMouseEnter={() => f.label_id && setHoveredLabelId(f.label_id)}
                        onMouseLeave={() => setHoveredLabelId(null)}
                      >
                        <td className="py-0.5 pr-2 text-gray-400 tabular-nums">{f.num}</td>
                        <td className="py-0.5 pr-2 text-gray-600 font-medium whitespace-nowrap">{f.field}</td>
                        <td className="py-0.5 pr-2 text-gray-800 break-all">{f.value || <span className="text-gray-300">—</span>}</td>
                        <td className="py-0.5 text-gray-400 font-mono text-[10px] whitespace-nowrap">{f.label_id || <span className="text-gray-300">—</span>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          {applying && (
            <p className="text-xs text-gray-400 text-center">Generating preview...</p>
          )}
          {applyResult && (
            <a
              href={downloadUrl(applyResult.session_id)}
              className="btn-secondary w-full text-sm py-2 text-center block"
              download
            >
              Download PDF
            </a>
          )}
        </ResizablePanel>
        <main className="flex-1 overflow-auto relative">
          <div className="absolute top-2 right-2 z-10 flex items-center gap-2">
            {previewSrc && pageCount > 1 && (
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setCurrentPage(p => Math.max(0, p - 1))}
                  disabled={currentPage === 0}
                  className="btn-ghost py-1 px-2 disabled:opacity-30"
                >
                  ← Prev
                </button>
                <span className="text-xs text-gray-500">{currentPage + 1} / {pageCount}</span>
                <button
                  onClick={() => setCurrentPage(p => Math.min(pageCount - 1, p + 1))}
                  disabled={currentPage === pageCount - 1}
                  className="btn-ghost py-1 px-2 disabled:opacity-30"
                >
                  Next →
                </button>
              </div>
            )}
            <ZoomControls zoom={zoom} onZoomChange={setZoom} />
          </div>
          {applyError
            ? <div className="flex items-center justify-center h-full text-red-400 text-sm p-4">{applyError}</div>
            : applying
              ? <div className="flex items-center justify-center h-full text-gray-400 text-sm">Generating preview...</div>
              : previewSrc
                ? <>
                    {applyResult?.warning && (
                      <div className="mx-4 mt-3 px-3 py-2 bg-amber-50 border border-amber-200 rounded text-xs text-amber-800">
                        ⚠ {applyResult.warning}
                      </div>
                    )}
                    <PdfViewer
                    url={previewSrc}
                    page={currentPage}
                    zoom={zoom}
                    onDimensions={handleDimensions}
                    overlay={
                      canvasDims && profileLabels.length > 0
                        ? <UserHighlightOverlay
                            canvasWidth={canvasDims.w}
                            canvasHeight={canvasDims.h}
                            pdfScale={canvasDims.scale}
                            currentPage={currentPage}
                            labels={profileLabels}
                            highlightedIds={highlightedIds}
                            hoveredLabelId={hoveredLabelId}
                            onHoverChange={setHoveredLabelId}
                          />
                        : undefined
                    }
                  /></>
                : <div className="flex items-center justify-center h-full text-gray-400 text-sm">Select a profile to preview</div>}
        </main>
      </div>
    </div>
  )
}
