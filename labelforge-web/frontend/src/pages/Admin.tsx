import React, { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { analyzeSession, deleteConfig, listConfigs, loadConfig, logout, previewUrl, saveEditableConfig, uploadFile } from '../api'
import type { ConfigSummary } from '../types'
import { AdminOverlay } from '../components/AdminOverlay'
import { LabelTable } from '../components/LabelTable'
import { PdfViewer } from '../components/PdfViewer'
import { useToast } from '../components/Toast'
import { UploadZone } from '../components/UploadZone'
import { useLabels } from '../context/LabelsContext'

type AdminTab = 'profiles' | 'labels'

export default function Admin() {
  const navigate = useNavigate()
  const { addToast } = useToast()
  const {
    labels, setLabels, sessionId, setSessionId,
    pageCount, setPageCount, currentPage, setCurrentPage,
    editableSet,
    loadEditableIds,
  } = useLabels()

  const [uploading, setUploading] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [savingConfig, setSavingConfig] = useState(false)
  const [canvasSize, setCanvasSize] = useState({ w: 800, h: 1000, scale: 1 })
  const [profiles, setProfiles] = useState<ConfigSummary[]>([])
  const [loadingProfiles, setLoadingProfiles] = useState(true)
  const [showUpload, setShowUpload] = useState(false)
  const [filename, setFilename] = useState('')
  const [profileName, setProfileName] = useState('')
  const [activeTab, setActiveTab] = useState<AdminTab>('profiles')

  // Guard: redirect if not admin
  useEffect(() => {
    const role = document.cookie.split('; ').find((r) => r.startsWith('role='))?.split('=')[1]
    if (role !== 'admin') navigate('/login')
  }, [navigate])

  const refreshProfiles = useCallback(async () => {
    try {
      const list = await listConfigs()
      setProfiles(list)
    } catch {}
  }, [])

  // Load profiles on mount
  useEffect(() => {
    refreshProfiles().finally(() => setLoadingProfiles(false))
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
        setActiveTab('labels')
      } catch (err) {
        addToast(String(err), 'error')
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
            setActiveTab('labels')
    } catch (err) {
      addToast(String(err), 'error')
    }
  }

  async function handleDeleteProfile(filename: string) {
    try {
      await deleteConfig(filename)
      setProfiles((prev) => prev.filter((c) => c.name !== filename))
      addToast(`Removed profile "${filename}"`, 'success')
    } catch (err) {
      addToast(String(err), 'error')
    }
  }

  const handleSaveConfig = useCallback(async () => {
    if (!sessionId) return
    setSavingConfig(true)
    try {
      const res = await saveEditableConfig(sessionId, [...editableSet], profileName.trim() || filename)
      addToast(`Saved ${res.saved} editable label(s).`, 'success')
      refreshProfiles()
    } catch (err) {
      addToast(String(err), 'error')
    } finally {
      setSavingConfig(false)
    }
  }, [sessionId, editableSet, addToast, refreshProfiles])

  const handleDimensions = useCallback(
    (w: number, h: number, scale: number) => setCanvasSize({ w, h, scale }),
    [],
  )

  async function handleLogout() {
    await logout()
    navigate('/login')
  }

  function handleBackToProfiles() {
    setSessionId(null)
    setLabels([])
    setFilename('')
        setActiveTab('profiles')
    refreshProfiles()
  }

  const hasSession = !!sessionId
  const editableCount = editableSet.size

  const tabs: { id: AdminTab; label: string }[] = [
    { id: 'profiles', label: 'Profiles' },
    { id: 'labels', label: 'Labels' },
  ]

  const pdfPanel = hasSession ? (
    <div className="flex flex-col flex-1 min-w-0 overflow-y-auto p-4 gap-3">
      <div className="flex items-center gap-3 justify-center">
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
      </div>
      <PdfViewer
        url={previewUrl(sessionId!)}
        page={currentPage}
        onPageCount={setPageCount}
        onDimensions={handleDimensions}
        overlay={
          <AdminOverlay
            canvasWidth={canvasSize.w}
            canvasHeight={canvasSize.h}
            pdfScale={canvasSize.scale}
            currentPage={currentPage}
          />
        }
      />
    </div>
  ) : null

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col">
      {/* Top bar */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-gray-800 bg-gray-900">
        <div className="flex items-center gap-3">
          <span className="text-xl">🏷️</span>
          <span className="font-bold text-gray-100">LabelForge</span>
          <span className="text-xs bg-brand-600 text-white px-2 py-0.5 rounded-full">Admin</span>
        </div>
        {filename && <span className="text-gray-400 text-sm truncate max-w-xs">{filename}</span>}
        <button onClick={handleLogout} className="btn-secondary text-sm py-1.5">Logout</button>
      </header>

      {/* Tab bar */}
      <div className="flex gap-1 px-4 pt-2 pb-0 border-b border-gray-800 bg-gray-900">
        {tabs.map((tab) => {
          const disabled = tab.id === 'labels' && !hasSession
          return (
            <button
              key={tab.id}
              onClick={() => !disabled && setActiveTab(tab.id)}
              disabled={disabled}
              className={`px-4 py-1.5 text-sm rounded-t transition-colors ${
                activeTab === tab.id
                  ? 'bg-gray-950 text-gray-100 border border-b-0 border-gray-700'
                  : disabled
                  ? 'text-gray-700 cursor-not-allowed'
                  : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* Content */}
      <div className="flex flex-1 overflow-hidden">

        {/* PROFILES TAB */}
        {activeTab === 'profiles' && (
          <div className="flex-1 overflow-y-auto">
            <div className="max-w-2xl mx-auto px-4 py-8 space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-gray-200 font-semibold">Profiles</h2>
                <button
                  onClick={() => setShowUpload((v) => !v)}
                  className="btn-secondary text-xs py-1.5 px-3"
                >
                  {showUpload ? 'Cancel' : '+ Add Profile'}
                </button>
              </div>

              {showUpload && (
                <div className="space-y-2">
                  <UploadZone onFile={handleFile} loading={uploading || analyzing} />
                  {analyzing && (
                    <p className="text-center text-gray-500 text-sm">Analyzing labels…</p>
                  )}
                </div>
              )}

              {loadingProfiles ? (
                <p className="text-gray-500 text-sm">Loading…</p>
              ) : profiles.length === 0 && !showUpload ? (
                <p className="text-gray-600 text-sm">No profiles yet. Click "+ Add Profile" to upload a file.</p>
              ) : (
                <div className="flex flex-col gap-2">
                  {profiles.map((cfg) => (
                    <div
                      key={cfg.name}
                      className="flex items-center justify-between gap-3 rounded-lg border border-gray-700 bg-gray-800/50 px-4 py-3"
                    >
                      <div className="min-w-0">
                        <div className="font-medium text-gray-200 text-sm truncate">{cfg.name || cfg.filename}</div>
                        {cfg.name && cfg.name !== cfg.filename && (
                          <div className="text-xs text-gray-600 truncate">{cfg.filename}</div>
                        )}
                        <div className="flex gap-3 mt-0.5 text-xs text-gray-600">
                          <span>{cfg.editable_count} editable</span>
                          <span>{cfg.page_count} page{cfg.page_count !== 1 ? 's' : ''}</span>
                          <span>.{cfg.file_type}</span>
                          <span>{new Date(cfg.updated_at).toLocaleDateString()}</span>
                        </div>
                      </div>
                      <div className="flex gap-2 shrink-0">
                        <button
                          onClick={() => handleLoadProfile(cfg)}
                          className="text-xs text-brand-400 hover:text-brand-300 transition-colors"
                          title="Load into Labels tab to edit"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => handleDeleteProfile(cfg.name)}
                          className="text-xs text-gray-600 hover:text-red-400 transition-colors"
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
        )}

        {/* LABELS TAB */}
        {activeTab === 'labels' && hasSession && (
          <>
            {pdfPanel}
            <div className="w-[30rem] shrink-0 border-l border-gray-800 bg-gray-900 flex flex-col overflow-hidden">
              {/* Header with Save Profile prominent at top */}
              <div className="px-4 py-3 border-b border-gray-800 space-y-2">
                <div className="flex items-center justify-between">
                  <button
                    onClick={handleBackToProfiles}
                    className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
                  >
                    ← Profiles
                  </button>
                  <span className="text-gray-600 text-xs">
                    {editableCount > 0 ? `${editableCount} editable` : 'none editable'}
                  </span>
                </div>
                <input
                  type="text"
                  value={profileName}
                  onChange={(e) => setProfileName(e.target.value)}
                  placeholder="Profile name…"
                  className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-brand-500"
                />
                <button
                  onClick={handleSaveConfig}
                  disabled={savingConfig}
                  className="btn-primary w-full text-sm py-2"
                >
                  {savingConfig ? 'Saving…' : 'Save Profile'}
                </button>
              </div>
              <div className="flex-1 overflow-y-auto p-3">
                <LabelTable />
              </div>
            </div>
          </>
        )}


      </div>
    </div>
  )
}

