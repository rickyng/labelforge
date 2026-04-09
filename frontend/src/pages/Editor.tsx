import React, { useCallback, useEffect, useMemo, useState } from 'react'
import {
  analyzeComponents,
  applyDirect,
  downloadUrl,
  listTemplates,
  loadAiFile,
  mapTemplateFields,
  outputPreviewUrl,
  previewImagesUrl,
  previewUrl,
  uploadFile,
} from '../api'
import type { ComponentMapResponse, DocumentComponent, Label, ProfileApplyResponse, TemplateSummary } from '../types'
import { AdminOverlay } from '../components/AdminOverlay'
import { ZoomControls } from '../components/ZoomControls'
import { PdfViewer } from '../components/PdfViewer'
import { useToast } from '../components/Toast'
import { UploadZone } from '../components/UploadZone'
import { IntendedValuesTable } from '../components/IntendedValuesTable'
import { FieldMappingTable } from '../components/FieldMappingTable'
import { LabelTable } from '../components/LabelTable'
import { useLabels } from '../context/LabelsContext'
import { TagIcon } from '../components/TagIcon'

function textComponentToLabel(c: DocumentComponent): Label {
  return {
    id: c.id,
    page: c.page,
    bbox: c.bbox,
    original_text: c.text ?? '',
    new_text: null,
    fontname: c.fontname ?? 'helv',
    fontsize: c.fontsize ?? 10,
    color: c.color ?? '#000000',
    flags: 0,
    rotation: 0,
    origin: null,
    auto_fit: true,
    max_scale_down: 0.5,
    padding: 0,
    white_out: false,
  }
}

export default function Editor() {
  const { addToast } = useToast()
  const {
    labels, setLabels,
    sessionId, setSessionId,
    pageCount, setPageCount,
    currentPage, setCurrentPage,
  } = useLabels()

  const [uploading, setUploading] = useState(false)
  const [canvasSize, setCanvasSize] = useState({ w: 800, h: 1000, scale: 1 })
  const [zoom, setZoom] = useState(1)
  const [filename, setFilename] = useState('')
  const [components, setComponents] = useState<DocumentComponent[]>([])
  const [templates, setTemplates] = useState<TemplateSummary[]>([])
  const [selectedTemplate, setSelectedTemplate] = useState<string>('')
  const [mappedData, setMappedData] = useState<ComponentMapResponse | null>(null)
  const [sizeIndex, setSizeIndex] = useState(0)
  const [analyzing, setAnalyzing] = useState(false)
  const [previewImageUrls, setPreviewImageUrls] = useState<string[]>([])
  const [pagePoints, setPagePoints] = useState<{ width: number; height: number } | null>(null)
  const [showOverlay, setShowOverlay] = useState(true)
  const [renderKey, setRenderKey] = useState(0)
  const [orderJsonFile, setOrderJsonFile] = useState<File | null>(null)
  const pdfScrollRef = React.useRef<HTMLDivElement>(null)

  // New state for edited view
  const [viewMode, setViewMode] = useState<'original' | 'edited'>('original')
  const [applyResult, setApplyResult] = useState<ProfileApplyResponse | null>(null)
  const [applying, setApplying] = useState(false)
  const [editedSessionId, setEditedSessionId] = useState<string | null>(null)
  const [editedPreviewImageUrls, setEditedPreviewImageUrls] = useState<string[]>([])
  const [editedPagePoints, setEditedPagePoints] = useState<{ width: number; height: number } | null>(null)
  const [panelWidthPct, setPanelWidthPct] = useState(25) // default 25%
  const panelResizeRef = React.useRef<{ startX: number; startPct: number; containerWidth: number } | null>(null)

  // Load templates on mount
  useEffect(() => {
    listTemplates()
      .then(res => setTemplates(res.templates))
      .catch(() => {})
  }, [])

  // Derive mapping count
  const changesForSize = mappedData?.changes?.[sizeIndex] ?? {}
  const mappedCount = Object.keys(changesForSize).length

  // Handle file upload (order JSON)
  const handleFile = useCallback(
    async (file: File) => {
      setUploading(true)
      try {
        const up = await uploadFile(file)
        setSessionId(up.session_id)
        setFilename(file.name)
        setOrderJsonFile(file)
        addToast(`Uploaded: ${file.name}`, 'success')
      } catch (err) {
        addToast(err instanceof Error ? err.message : 'Upload failed', 'error')
      } finally {
        setUploading(false)
      }
    },
    [addToast, setSessionId],
  )

  // Ref to always get the latest orderJsonFile in effects without adding it to deps
  const orderJsonFileRef = React.useRef<File | null>(null)
  orderJsonFileRef.current = orderJsonFile

  // Load AI file preview when template is selected
  useEffect(() => {
    if (!selectedTemplate || !sessionId) {
      setPreviewImageUrls([])
      setPagePoints(null)
      setMappedData(null)
      setLabels([])
      setComponents([])
      return
    }
    setAnalyzing(true)
    setLabels([])
    setMappedData(null)
    loadAiFile(selectedTemplate, sessionId)
      .then(aiRes => {
        setPageCount(aiRes.page_count)
        setCurrentPage(0)
        setRenderKey(k => k + 1)
        addToast(`Loaded template — ${aiRes.labels.length} label(s)`, 'success')
        fetchComponents(aiRes.session_id)
        fetchPreviewImages(aiRes.session_id)
        // Map template fields against the uploaded order JSON
        const currentFile = orderJsonFileRef.current
        if (currentFile) {
          return mapTemplateFields(selectedTemplate, currentFile, sessionId)
        }
        return null
      })
      .then(mapRes => {
        if (mapRes) {
          setMappedData(mapRes)
          setSizeIndex(0)
        }
      })
      .catch(err => addToast(err instanceof Error ? err.message : 'Failed to load template', 'error'))
      .finally(() => setAnalyzing(false))
  }, [selectedTemplate, sessionId]) // eslint-disable-line react-hooks/exhaustive-deps

  // Reset edited state only when template changes (not size)
  useEffect(() => {
    setViewMode('original')
    setEditedSessionId(null)
    setApplyResult(null)
    setEditedPreviewImageUrls([])
    setEditedPagePoints(null)
  }, [selectedTemplate])

  // Re-apply when size changes and user was viewing edited
  useEffect(() => {
    if (viewMode === 'edited' && editedSessionId && sessionId && selectedTemplate) {
      handleApply()
    }
  }, [sizeIndex]) // eslint-disable-line react-hooks/exhaustive-deps

  async function fetchComponents(sid: string) {
    try {
      const res = await analyzeComponents(sid)
      setComponents(res.components)
      const textLabels = res.components
        .filter(c => c.type === 'TEXT')
        .map(textComponentToLabel)
      setLabels(textLabels)
    } catch {}
  }

  async function fetchPreviewImages(sid: string, edited: boolean = false) {
    const setUrls = edited ? setEditedPreviewImageUrls : setPreviewImageUrls
    const setPts = edited ? setEditedPagePoints : setPagePoints
    try {
      const res = await fetch(previewImagesUrl(sid), { credentials: 'include' })
      if (!res.ok) { setUrls([]); return }
      const data = await res.json()
      const urls: string[] = data.pages.map((p: { page: number; url: string }) => p.url)
      setUrls(urls)
      if (data.page_width && data.page_height) {
        setPts({ width: data.page_width, height: data.page_height })
      }
    } catch {
      setUrls([])
    }
  }

  const handleDimensions = useCallback(
    (w: number, h: number, scale: number) => setCanvasSize({ w, h, scale }),
    [],
  )

  const handlePanelResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    const container = (e.currentTarget.parentElement as HTMLDivElement)
    panelResizeRef.current = { startX: e.clientX, startPct: panelWidthPct, containerWidth: container.clientWidth }
    const onMove = (ev: MouseEvent) => {
      if (!panelResizeRef.current) return
      const dx = ev.clientX - panelResizeRef.current.startX
      const pctDelta = (dx / panelResizeRef.current.containerWidth) * 100
      setPanelWidthPct(Math.max(10, Math.min(90, panelResizeRef.current.startPct + pctDelta)))
    }
    const onUp = () => {
      panelResizeRef.current = null
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }, [panelWidthPct])

  // Apply changes
  async function handleApply() {
    if (!sessionId || !selectedTemplate) return
    setApplying(true)
    try {
      const result = await applyDirect(selectedTemplate, sessionId, sizeIndex)
      setApplyResult(result)
      setEditedSessionId(result.session_id)
      setViewMode('edited')
      setRenderKey(k => k + 1)
      fetchPreviewImages(result.session_id, true)
      if (result.warning) addToast(result.warning, 'warning')
      addToast(`Applied ${result.changed_count} change(s)`, 'success')
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Apply failed', 'error')
    } finally {
      setApplying(false)
    }
  }

  const hasSession = !!sessionId
  const hasTemplate = hasSession && selectedTemplate

  const pdfPanel = hasTemplate ? (
    <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
      <div className="flex items-center gap-3 justify-center flex-wrap shrink-0 px-4 pt-4 pb-2">
        <button
          onClick={() => setCurrentPage(Math.max(0, currentPage - 1))}
          disabled={currentPage === 0}
          className="btn-secondary text-sm py-1 px-3"
        >
          ‹ Prev
        </button>
        <span className="text-gray-400 text-sm">Page {currentPage + 1} / {pageCount}</span>
        <button
          onClick={() => setCurrentPage(Math.min(pageCount - 1, currentPage + 1))}
          disabled={currentPage >= pageCount - 1}
          className="btn-secondary text-sm py-1 px-3"
        >
          Next ›
        </button>
        <ZoomControls
          zoom={zoom}
          onZoomChange={setZoom}
          className="ml-2"
          btnClassName="btn-secondary text-sm py-1 px-2"
        />
        {/* Original / Edited toggle */}
        {mappedCount > 0 && (
          <div className="flex rounded border border-gray-300 overflow-hidden">
            <button
              onClick={() => setViewMode('original')}
              className={`text-xs py-1 px-3 ${viewMode === 'original' ? 'bg-gray-900 text-white' : 'bg-white text-gray-600 hover:bg-gray-100'}`}
            >
              Original
            </button>
            <button
              onClick={() => {
                if (viewMode === 'original' && !editedSessionId) {
                  handleApply()
                } else {
                  setViewMode('edited')
                }
              }}
              disabled={applying}
              className={`text-xs py-1 px-3 ${viewMode === 'edited' ? 'bg-gray-900 text-white' : 'bg-white text-gray-600 hover:bg-gray-100'} disabled:opacity-50`}
            >
              {applying ? 'Applying...' : 'Edited'}
            </button>
          </div>
        )}
        <button
          onClick={() => setShowOverlay(v => !v)}
          className={`btn-secondary text-xs py-1 px-2 ${showOverlay ? 'bg-gray-900 text-white hover:bg-gray-700' : ''}`}
          title={showOverlay ? 'Hide overlay' : 'Show overlay'}
        >
          {showOverlay ? 'Boxes ON' : 'Boxes OFF'}
        </button>
        {/* Download button */}
        {editedSessionId && (
          <a
            href={downloadUrl(editedSessionId)}
            download
            className="btn-primary text-xs py-1 px-3 flex items-center gap-1"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v12m0 0l-4-4m4 4l4-4M4 18h16" />
            </svg>
            Download
          </a>
        )}
      </div>
      <div className="flex-1 overflow-auto px-4 pb-4" ref={pdfScrollRef}>
        <PdfViewer
          key={`pdf-${renderKey}`}
          url={
            viewMode === 'edited' && editedSessionId
              ? `${outputPreviewUrl(editedSessionId)}?_=${renderKey}`
              : `${previewUrl(sessionId!)}?_=${renderKey}`
          }
          page={currentPage}
          zoom={zoom}
          onPageCount={setPageCount}
          onDimensions={handleDimensions}
          scrollContainerRef={pdfScrollRef}
          imageUrl={
            viewMode === 'edited' && editedPreviewImageUrls[currentPage]
              ? `${editedPreviewImageUrls[currentPage]}?_=${renderKey}`
              : viewMode === 'original' && previewImageUrls[currentPage]
                ? `${previewImageUrls[currentPage]}?_=${renderKey}`
                : undefined
          }
          pagePoints={
            viewMode === 'edited' && editedPagePoints
              ? editedPagePoints
              : pagePoints ?? undefined
          }
          overlay={showOverlay && viewMode === 'original' ? (
            <AdminOverlay
              canvasWidth={canvasSize.w}
              canvasHeight={canvasSize.h}
              pdfScale={canvasSize.scale}
              currentPage={currentPage}
              components={components}
            />
          ) : undefined}
        />
      </div>
    </div>
  ) : hasSession ? (
    <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
      <p>Select a template to preview</p>
    </div>
  ) : null

  return (
    <div className="h-screen bg-white flex flex-col overflow-hidden">
      {/* Top bar */}
      <header className="flex items-center justify-between px-6 py-3 border-b-2 border-gray-900 bg-[#FAFAFA]">
        <div className="flex items-center gap-3">
          <TagIcon className="w-5 h-5 text-brand-600" />
          <span className="font-bold text-gray-900">LabelForge</span>
        </div>
        {filename && <span className="text-gray-500 text-sm truncate max-w-xs">{filename}</span>}
      </header>

      {/* Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left panel */}
        <div className="border-r border-gray-200 bg-white flex flex-col overflow-hidden relative" style={{ width: `${panelWidthPct}%` }}>
          {/* Resize handle */}
          <div
            className="absolute top-0 right-0 bottom-0 w-1.5 cursor-col-resize hover:bg-blue-300 active:bg-blue-400 z-10"
            onMouseDown={handlePanelResizeStart}
          />
          {/* Upload */}
          {!hasSession && (
            <div className="flex-1 flex items-center justify-center p-4">
              <UploadZone onFile={handleFile} loading={uploading} />
            </div>
          )}

          {/* Controls */}
          {hasSession && (
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {/* Template selector */}
              <div>
                <label className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1 block">Template</label>
                <select
                  className="w-full border rounded px-2 py-1 text-sm disabled:opacity-50"
                  value={selectedTemplate}
                  onChange={e => setSelectedTemplate(e.target.value)}
                  disabled={analyzing}
                >
                  <option value="">-- Select template --</option>
                  {templates.map(t => (
                    <option key={t.name} value={t.name}>{t.name} ({t.field_count} fields)</option>
                  ))}
                </select>
                {analyzing && <p className="text-xs text-gray-400 mt-1">Loading…</p>}
              </div>

              {/* Size navigation */}
              {mappedData && mappedData.size_names.length > 0 && (
                <div>
                  <label className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1 block">Size</label>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setSizeIndex(Math.max(0, sizeIndex - 1))}
                      disabled={sizeIndex === 0}
                      className="btn-secondary text-xs py-0.5 px-2"
                    >‹</button>
                    <span className="text-sm text-gray-600 tabular-nums flex-1 text-center">
                      {mappedData.size_names[sizeIndex] ?? `Size ${sizeIndex + 1}`}
                    </span>
                    <button
                      onClick={() => setSizeIndex(Math.min(mappedData.size_names.length - 1, sizeIndex + 1))}
                      disabled={sizeIndex >= mappedData.size_names.length - 1}
                      className="btn-secondary text-xs py-0.5 px-2"
                    >›</button>
                  </div>
                </div>
              )}

              {/* Field mapping: PDF field / JSON path / value */}
              {mappedData && mappedData.fields.length > 0 && (
                <div>
                  <label className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1 block">
                    Field Mapping ({mappedData.fields.filter(f => f.field_type !== 'unmapped').length})
                  </label>
                  <FieldMappingTable
                    fields={mappedData.fields}
                    sizeIndex={sizeIndex}
                  />
                </div>
              )}

              {/* Intended values: component ID ↔ value from mapping */}
              {mappedData && Object.keys(changesForSize).length > 0 && (
                <div>
                  <label className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1 block">
                    Intended Values ({mappedCount})
                  </label>
                  <IntendedValuesTable changes={changesForSize} />
                </div>
              )}

              {/* Component table with type filter */}
              {(labels.length > 0 || components.length > 0) && (
                <div>
                  <label className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1 block">
                    Components
                  </label>
                  <LabelTable changesForSize={changesForSize} components={components} />
                </div>
              )}

              {/* Clear button */}
              <button
                onClick={() => {
                  setSessionId(null)
                  setLabels([])
                  setFilename('')
                  setSelectedTemplate('')
                  setMappedData(null)
                  setSizeIndex(0)
                  setPreviewImageUrls([])
                  setPagePoints(null)
                  setViewMode('original')
                  setEditedSessionId(null)
                  setApplyResult(null)
                  setOrderJsonFile(null)
                  setEditedPreviewImageUrls([])
                  setEditedPagePoints(null)
                }}
                className="w-full btn-secondary text-sm py-1"
              >
                Clear Session
              </button>
            </div>
          )}
        </div>

        {/* Right panel: PDF preview */}
        {pdfPanel}
      </div>
    </div>
  )
}
