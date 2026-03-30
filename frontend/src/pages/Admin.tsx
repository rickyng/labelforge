import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { analyzeComponents, analyzeSession, deleteConfig, importJson, listConfigs, loadConfig, logout, previewUrl, saveEditableConfig, uploadFile } from '../api'
import type { ConfigSummary, DocumentComponent, ImportJsonResponse } from '../types'
import { AdminOverlay } from '../components/AdminOverlay'
import { ZoomControls } from '../components/ZoomControls'
import { LabelTable } from '../components/LabelTable'
import { PdfViewer } from '../components/PdfViewer'
import { useToast } from '../components/Toast'
import { UploadZone } from '../components/UploadZone'
import { JsonUploadZone } from '../components/JsonUploadZone'
import { useLabels } from '../context/LabelsContext'
import { TagIcon } from '../components/TagIcon'
import { ResizablePanel } from '../components/ResizablePanel'
import { getRole } from '../utils/auth'

export default function Admin() {
  const navigate = useNavigate()
  const { addToast } = useToast()
  const {
    labels, setLabels, updateLabel, sessionId, setSessionId,
    pageCount, setPageCount, currentPage, setCurrentPage,
    editableSet,
    loadEditableIds,
  } = useLabels()

  const labelsRef = useRef(labels)
  useEffect(() => { labelsRef.current = labels }, [labels])

  const [uploading, setUploading] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [savingConfig, setSavingConfig] = useState(false)
  const [canvasSize, setCanvasSize] = useState({ w: 800, h: 1000, scale: 1 })
  const [zoom, setZoom] = useState(1)
  const [profiles, setProfiles] = useState<ConfigSummary[]>([])
  const [loadingProfiles, setLoadingProfiles] = useState(true)
  const [showUpload, setShowUpload] = useState(false)
  const [filename, setFilename] = useState('')
  const [profileName, setProfileName] = useState('')
  const [components, setComponents] = useState<DocumentComponent[]>([])
  const [jsonImportLoading, setJsonImportLoading] = useState(false)
  const [jsonImportResult, setJsonImportResult] = useState<ImportJsonResponse | null>(null)
  const [selectedImportSize, setSelectedImportSize] = useState<string>('')

  // Guard: redirect if not admin
  useEffect(() => {
    if (getRole() !== 'admin') navigate('/login')
  }, [navigate])

  const refreshProfiles = useCallback(async () => {
    try {
      const list = await listConfigs()
      setProfiles(list)
    } catch {}
  }, [])

  // Load profiles on mount
  useEffect(() => {
    let cancelled = false
    refreshProfiles().finally(() => { if (!cancelled) setLoadingProfiles(false) })
    return () => { cancelled = true }
  }, [refreshProfiles])

  const handleFile = useCallback(
    async (file: File) => {
      setUploading(true)
      try {
        const up = await uploadFile(file)
        setFilename(file.name)
        setProfileName(file.name)
        if (up.warning) addToast(up.warning, 'warning')
        else addToast(`Uploaded: ${file.name}`, 'success')

        setAnalyzing(true)
        const res = await analyzeSession(up.session_id)
        setSessionId(res.session_id)
        setLabels(res.labels)
        setPageCount(res.page_count)
        setCurrentPage(0)
        loadEditableIds(res.editable_ids)
        if (res.warning) addToast(res.warning, 'warning')
        addToast(`Extracted ${res.labels.length} label(s)`, 'success')
        setShowUpload(false)
        fetchComponents(res.session_id)
      } catch (err) {
        addToast(err instanceof Error ? err.message : 'An error occurred', 'error')
      } finally {
        setUploading(false)
        setAnalyzing(false)
      }
    },
    [addToast, setLabels, setPageCount, setCurrentPage, setSessionId, loadEditableIds],
  )

  async function handleLoadProfile(cfg: ConfigSummary) {
    try {
      const res = await loadConfig(cfg.name)
      setSessionId(res.session_id)
      setLabels(res.labels)
      setPageCount(res.page_count)
      setCurrentPage(0)
      loadEditableIds(res.editable_ids)
      setFilename(cfg.filename)
      setProfileName(cfg.name || cfg.filename)
      setJsonImportResult(null)
      setSelectedImportSize('')
      fetchComponents(res.session_id)
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'An error occurred', 'error')
    }
  }

  async function handleDeleteProfile(filename: string) {
    try {
      await deleteConfig(filename)
      setProfiles((prev) => prev.filter((c) => c.name !== filename))
      addToast(`Removed profile "${filename}"`, 'success')
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'An error occurred', 'error')
    }
  }

  const handleSaveConfig = useCallback(async () => {
    if (!sessionId) return
    const name = profileName.trim()
    if (!name) {
      addToast('Enter a profile name before saving.', 'error')
      return
    }
    setSavingConfig(true)
    try {
      const res = await saveEditableConfig(sessionId, [...editableSet], name)
      addToast(`Saved ${res.saved} editable label(s).`, 'success')
      await refreshProfiles()
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'An error occurred', 'error')
    } finally {
      setSavingConfig(false)
    }
  }, [sessionId, editableSet, profileName, addToast, refreshProfiles])

  async function fetchComponents(sid: string) {
    try {
      const res = await analyzeComponents(sid)
      setComponents(res.components)
    } catch {
      // non-critical — overlay simply won't show components
    }
  }

  // Auto-select first size when JSON is imported
  useEffect(() => {
    if (jsonImportResult?.sizes?.length) {
      setSelectedImportSize(jsonImportResult.sizes[0])
    }
  }, [jsonImportResult])

  // Auto-populate editableSet and new_text when selected size changes
  useEffect(() => {
    if (!selectedImportSize || !jsonImportResult) return
    const changes = jsonImportResult.changes_by_size[selectedImportSize] ?? {}
    loadEditableIds(Object.keys(changes))
    labelsRef.current.forEach(lbl => {
      const val = changes[lbl.id]
      updateLabel(lbl.id, { new_text: val !== undefined ? val : null })
    })
  }, [selectedImportSize, jsonImportResult, loadEditableIds, updateLabel])

  const handleJsonFile = useCallback(async (file: File) => {
    if (!sessionId) return
    setJsonImportLoading(true)
    try {
      const res = await importJson(sessionId, file)
      setJsonImportResult(res)
      addToast(`Imported ${res.sizes.length} size(s) from ${res.source_file}`, 'success')
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Import failed', 'error')
    } finally {
      setJsonImportLoading(false)
    }
  }, [sessionId, addToast])

  const handleDimensions = useCallback(
    (w: number, h: number, scale: number) => setCanvasSize({ w, h, scale }),
    [],
  )

  async function handleLogout() {
    await logout()
    navigate('/login')
  }

  function handleClearSession() {
    setSessionId(null)
    setLabels([])
    setFilename('')
    setProfileName('')
    setJsonImportResult(null)
    setSelectedImportSize('')
    refreshProfiles()
  }

  const hasSession = !!sessionId
  const editableCount = editableSet.size

  const pdfPanel = hasSession ? (
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
      </div>
      <div className="flex-1 overflow-auto px-4 pb-4">
        <PdfViewer
          url={previewUrl(sessionId!)}
          page={currentPage}
          zoom={zoom}
          onPageCount={setPageCount}
          onDimensions={handleDimensions}
          overlay={
            <AdminOverlay
              canvasWidth={canvasSize.w}
              canvasHeight={canvasSize.h}
              pdfScale={canvasSize.scale}
              currentPage={currentPage}
              components={components}
            />
          }
        />
      </div>
    </div>
  ) : null

  return (
    <div className="h-screen bg-white flex flex-col overflow-hidden">
      {/* Top bar */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-gray-200 bg-white shadow-sm">
        <div className="flex items-center gap-3">
          <TagIcon className="w-5 h-5 text-brand-600" />
          <span className="font-bold text-gray-900">LabelForge</span>
          <span className="text-xs bg-brand-600 text-white px-2 py-0.5 rounded-full">Admin</span>
        </div>
        {filename && <span className="text-gray-500 text-sm truncate max-w-xs">{filename}</span>}
        <button onClick={handleLogout} className="btn-secondary text-sm py-1.5">Logout</button>
      </header>

      {/* Content */}
      <div className="flex flex-1 overflow-hidden">

        {/* LEFT: Profiles sidebar */}
        <ResizablePanel defaultWidth={320} minWidth={200} maxWidth={560} className="border-r border-gray-200 bg-white flex flex-col overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
            <h2 className="font-semibold text-gray-900 text-sm">Profiles</h2>
            <button
              onClick={() => setShowUpload((v) => !v)}
              className="btn-secondary text-xs py-1.5 px-3"
            >
              {showUpload ? 'Cancel' : '+ Add Profile'}
            </button>
          </div>
          <div className="flex-1 overflow-y-auto">
          <div className="px-4 py-4 space-y-4">
              {showUpload && (
                <div className="space-y-2">
                  <UploadZone onFile={handleFile} loading={uploading || analyzing} />
                  {analyzing && (
                    <p className="text-center text-gray-500 text-sm">Analyzing labels…</p>
                  )}
                </div>
              )}

              {loadingProfiles ? (
                <p className="text-gray-400 text-sm">Loading…</p>
              ) : profiles.length === 0 && !showUpload ? (
                <p className="text-gray-500 text-sm">No profiles yet. Click "+ Add Profile" to upload a file.</p>
              ) : (
                <div className="flex flex-col gap-2">
                  {profiles.map((cfg) => (
                    <div
                      key={cfg.name}
                      className={`flex items-center justify-between gap-3 rounded-lg border px-4 py-3 cursor-pointer transition-colors ${
                        profileName === cfg.name
                          ? 'border-brand-500 bg-brand-50'
                          : 'border-gray-200 bg-gray-50 hover:border-gray-300'
                      }`}
                      onClick={() => handleLoadProfile(cfg)}
                    >
                      <div className="min-w-0">
                        <div className="font-medium text-gray-800 text-sm truncate">{cfg.name || cfg.filename}</div>
                        {cfg.name && cfg.name !== cfg.filename && (
                          <div className="text-xs text-gray-400 truncate">{cfg.filename}</div>
                        )}
                        <div className="flex gap-3 mt-0.5 text-xs text-gray-500">
                          <span>{cfg.editable_count} editable</span>
                          <span>{cfg.page_count}p</span>
                          <span>.{cfg.file_type}</span>
                        </div>
                      </div>
                      <div className="flex gap-2 shrink-0">
                        <button
                          onClick={(e) => { e.stopPropagation(); handleDeleteProfile(cfg.name) }}
                          className="text-xs text-gray-400 hover:text-red-500 transition-colors"
                          title="Remove profile"
                        >
           Remove
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </ResizablePanel>

        {/* RIGHT: PDF preview + label editor (shown when a profile is loaded) */}
        {hasSession && (
          <>
            {pdfPanel}
            <ResizablePanel defaultWidth={600} minWidth={280} maxWidth={720} side="right" className="border-l border-gray-200 bg-white flex flex-col overflow-hidden">
              {/* Header */}
              <div className="px-4 py-3 border-b border-gray-200 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-gray-900 truncate">{profileName || filename}</span>
                  <div className="flex items-center gap-3">
                    <span className="text-gray-400 text-xs">
                      {editableCount > 0 ? `${editableCount} editable` : 'none editable'}
                    </span>
                    <button
                      onClick={handleClearSession}
                      className="text-gray-400 hover:text-gray-600 transition-colors cursor-pointer"
                      aria-label="Close"
                    >
                      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
                    </button>
                  </div>
                </div>
                <input
                  type="text"
                  value={profileName}
                  onChange={(e) => setProfileName(e.target.value)}
                  placeholder="Profile name…"
                  className="input-field"
                />
                <button
                  onClick={handleSaveConfig}
                  disabled={savingConfig}
                  className="btn-primary w-full text-sm py-2"
                >
                  {savingConfig ? 'Saving…' : 'Save Profile'}
                </button>
              </div>

              <div className="px-4 pb-4">
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Order JSON</p>
                <JsonUploadZone
                  onFile={handleJsonFile}
                  loading={jsonImportLoading}
                  result={jsonImportResult}
                />
              </div>

              {jsonImportResult && jsonImportResult.sizes.length > 0 && (
                <div className="px-4 pb-2 space-y-2">
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Preview Size</p>
                  <select
                    className="w-full border rounded px-2 py-1 text-sm"
                    value={selectedImportSize}
                    onChange={e => setSelectedImportSize(e.target.value)}
                  >
                    {jsonImportResult.sizes.map(s => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                  {selectedImportSize && (() => {
                    const fields = jsonImportResult.fields_by_size[selectedImportSize] ?? []
                    return fields.length > 0 ? (
                      <div className="border rounded bg-gray-50 max-h-64 overflow-y-auto">
                        <table className="w-full text-xs">
                          <thead className="sticky top-0 bg-gray-100 z-10">
                            <tr className="border-b text-gray-500">
                              <th className="py-1 px-2 text-left font-medium w-8">#</th>
                              <th className="py-1 px-2 text-left font-medium">Field</th>
                              <th className="py-1 px-2 text-left font-medium">Value</th>
                            </tr>
                          </thead>
                          <tbody>
                            {fields.map(f => (
                              <tr key={f.num} className="border-b border-gray-100 last:border-0">
                                <td className="py-0.5 px-2 text-gray-400 tabular-nums">{f.num}</td>
                                <td className="py-0.5 px-2 font-medium text-gray-600 whitespace-nowrap">{f.field}</td>
                                <td className="py-0.5 px-2 text-gray-800 font-mono" title={f.path}>{f.value || <span className="text-gray-300">—</span>}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : null
                  })()}
                </div>
              )}

              <div className="flex-1 overflow-y-auto p-3">
                <LabelTable changesForSize={
                  selectedImportSize && jsonImportResult
                    ? (jsonImportResult.changes_by_size[selectedImportSize] ?? {})
                    : {}
                } />
              </div>
            </ResizablePanel>
          </>
        )}

      </div>
    </div>
  )
}

