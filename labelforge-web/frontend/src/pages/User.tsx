import React, { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  applyLabels, deleteUserLabel, downloadUrl, listConfigs, listUserLabels,
  loadConfig, loadUserLabel, logout, previewUrl, saveUserLabel,
} from '../api'
import { AdminOverlay } from '../components/AdminOverlay'
import { PdfViewer } from '../components/PdfViewer'
import { useToast } from '../components/Toast'
import { UserForm } from '../components/UserForm'
import { useLabels } from '../context/LabelsContext'
import type { ConfigSummary, UserLabelSummary } from '../types'

export default function User() {
  const navigate = useNavigate()
  const { addToast } = useToast()
  const {
    setLabels, sessionId, setSessionId,
    pageCount, setPageCount, currentPage, setCurrentPage,
    isDone, setIsDone,
    editableLabels,
    loadEditableIds,
  } = useLabels()

  // List view state
  const [userLabels, setUserLabels] = useState<UserLabelSummary[]>([])
  const [loadingList, setLoadingList] = useState(true)

  // Editor state
  const [activeLabel, setActiveLabel] = useState<string | null>(null) // null = list view
  const [labelName, setLabelName] = useState('')
  const [selectedProfile, setSelectedProfile] = useState('')
  const [profiles, setProfiles] = useState<ConfigSummary[]>([])
  const [loadingProfile, setLoadingProfile] = useState(false)
  const [applying, setApplying] = useState(false)
  const [saving, setSaving] = useState(false)
  const [outputFormat, setOutputFormat] = useState<'pdf' | 'ai'>('pdf')
  const [canvasSize, setCanvasSize] = useState({ w: 800, h: 1000, scale: 1 })

  // Guard: redirect if not logged in
  useEffect(() => {
    const role = document.cookie.split('; ').find((r) => r.startsWith('role='))?.split('=')[1]
    if (!role || (role !== 'admin' && role !== 'user')) navigate('/login')
  }, [navigate])

  // Load label list on mount
  useEffect(() => {
    listUserLabels()
      .then(setUserLabels)
      .catch(() => {})
      .finally(() => setLoadingList(false))
  }, [])

  // Load profiles for dropdown when entering editor
  async function loadProfiles() {
    try {
      const list = await listConfigs()
      setProfiles(list)
    } catch {}
  }

  async function openNewEditor() {
    setActiveLabel('')
    setLabelName('')
    setSelectedProfile('')
    setSessionId(null)
    setLabels([])
    setIsDone(false)
    await loadProfiles()
  }

  async function openExistingEditor(ul: UserLabelSummary) {
    try {
      const res = await loadUserLabel(ul.name)
      setSessionId(res.session_id)
      setLabels(res.labels)
      setPageCount(res.page_count)
      setCurrentPage(0)
      loadEditableIds(res.editable_ids)
      setIsDone(false)
      setActiveLabel(ul.name)
      setLabelName(ul.name)
      setSelectedProfile(ul.profile_name)
      await loadProfiles()
    } catch (err) {
      addToast(String(err), 'error')
    }
  }

  async function handleProfileChange(profileName: string) {
    setSelectedProfile(profileName)
    if (!profileName) return
    setLoadingProfile(true)
    try {
      const res = await loadConfig(profileName)
      setSessionId(res.session_id)
      setLabels(res.labels)
      setPageCount(res.page_count)
      setCurrentPage(0)
      loadEditableIds(res.editable_ids)
      setIsDone(false)
    } catch (err) {
      addToast(String(err), 'error')
    } finally {
      setLoadingProfile(false)
    }
  }

  async function handleSaveLabel() {
    if (!labelName.trim()) { addToast('Enter a label name.', 'error'); return }
    if (!selectedProfile) { addToast('Select a profile.', 'error'); return }
    setSaving(true)
    try {
      const fills: Record<string, string> = {}
      for (const lbl of editableLabels) {
        if (lbl.new_text !== null) fills[lbl.id] = lbl.new_text
      }
      await saveUserLabel(labelName.trim(), selectedProfile, fills)
      addToast('Label saved.', 'success')
      setActiveLabel(labelName.trim())
      const list = await listUserLabels()
      setUserLabels(list)
    } catch (err) {
      addToast(String(err), 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleGenerate = useCallback(async () => {
    if (!sessionId) return
    setApplying(true)
    try {
      const toApply = editableLabels.filter((l) => l.new_text !== null)
      const res = await applyLabels(sessionId, toApply, outputFormat)
      if (res.warning) addToast(res.warning, 'warning')
      addToast(`Applied ${res.changed_count} change(s). Ready to download.`, 'success')
      setIsDone(true)
    } catch (err) {
      addToast(String(err), 'error')
    } finally {
      setApplying(false)
    }
  }, [sessionId, editableLabels, outputFormat, addToast, setIsDone])

  async function handleDeleteLabel(name: string) {
    try {
      await deleteUserLabel(name)
      setUserLabels((prev) => prev.filter((l) => l.name !== name))
      addToast(`Deleted "${name}".`, 'success')
    } catch (err) {
      addToast(String(err), 'error')
    }
  }

  function handleBackToList() {
    setActiveLabel(null)
    setSessionId(null)
    setLabels([])
    setIsDone(false)
  }

  const handleDimensions = useCallback(
    (w: number, h: number, scale: number) => setCanvasSize({ w, h, scale }),
    [],
  )

  async function handleLogout() {
    await logout()
    navigate('/login')
  }

  const hasSession = !!sessionId
  const editedCount = editableLabels.filter((l) => l.new_text !== null).length
  const isEditorOpen = activeLabel !== null

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col">
      {/* Top bar */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-gray-800 bg-gray-900">
        <div className="flex items-center gap-3">
          <span className="text-xl">🏷️</span>
          <span className="font-bold text-gray-100">LabelForge</span>
        </div>
        {isEditorOpen && (
          <button
            onClick={handleBackToList}
            className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
          >
            ← Labels
          </button>
        )}
        <button onClick={handleLogout} className="btn-secondary text-sm py-1.5">Logout</button>
      </header>

      {/* LIST VIEW */}
      {!isEditorOpen && (
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-2xl mx-auto px-4 py-8 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-gray-200 font-semibold">Labels</h2>
              <button onClick={openNewEditor} className="btn-primary text-sm py-1.5 px-4">+ Add</button>
            </div>
            {loadingList ? (
              <p className="text-gray-500 text-sm">Loading…</p>
            ) : userLabels.length === 0 ? (
              <p className="text-gray-600 text-sm">No labels yet. Click "+ Add" to create one.</p>
            ) : (
              <div className="flex flex-col gap-2">
                {userLabels.map((ul) => (
                  <div
                    key={ul.name}
                    className="flex items-center justify-between gap-3 rounded-lg border border-gray-700 bg-gray-800/50 px-4 py-3"
                  >
                    <div className="min-w-0">
                      <div className="font-medium text-gray-200 text-sm truncate">{ul.name}</div>
                      <div className="text-xs text-gray-600 mt-0.5">{ul.profile_name} · {new Date(ul.updated_at).toLocaleDateString()}</div>
                    </div>
                    <div className="flex gap-2 shrink-0">
                      <button
                        onClick={() => openExistingEditor(ul)}
                        className="text-xs text-brand-400 hover:text-brand-300 transition-colors"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDeleteLabel(ul.name)}
                        className="text-xs text-gray-600 hover:text-red-400 transition-colors"
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
      {/* EDITOR VIEW */}
      {isEditorOpen && (
        <div className='flex flex-1 overflow-hidden'>
          {/* Left panel */}
          <div className='w-80 shrink-0 flex flex-col border-r border-gray-800 bg-gray-900 overflow-hidden'>
            <div className='p-4 space-y-3 border-b border-gray-800 shrink-0'>
              {/* Back + heading */}
              <div className='flex items-center gap-2'>
                <button
                  onClick={handleBackToList}
                  className='text-xs text-gray-500 hover:text-gray-300 transition-colors'
                >
                  ← Labels
                </button>
              </div>
              {/* Profile dropdown */}
              <div>
                <label className='block text-xs text-gray-500 mb-1'>Profile</label>
                <select
                  value={selectedProfile}
                  onChange={(e) => handleProfileChange(e.target.value)}
                  disabled={loadingProfile}
                  className='w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-brand-500'
                >
                  <option value=''>— select profile —</option>
                  {profiles.map((p) => (
                    <option key={p.name} value={p.name}>{p.name}</option>
                  ))}
                </select>
              </div>
              {/* Label name */}
              <div>
                <label className='block text-xs text-gray-500 mb-1'>Label name</label>
                <input
                  type='text'
                  value={labelName}
                  onChange={(e) => setLabelName(e.target.value)}
                  placeholder='e.g. Client X'
                  className='w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-brand-500'
                />
              </div>
              {/* Save Label */}
              <button
                onClick={handleSaveLabel}
                disabled={saving}
                className='btn-secondary text-xs py-1.5 w-full'
              >
                {saving ? 'Saving…' : 'Save Label'}
              </button>
              {/* Format picker + Generate */}
              <div className='space-y-1.5'>
                <label className='block text-xs text-gray-500'>Output format</label>
                <div className='flex rounded overflow-hidden border border-gray-700'>
                  <button
                    onClick={() => setOutputFormat('pdf')}
                    className={`flex-1 text-xs py-1.5 transition-colors ${
                      outputFormat === 'pdf'
                        ? 'bg-brand-600 text-white'
                        : 'bg-gray-800 text-gray-400 hover:text-gray-200'
                    }`}
                  >
                    PDF
                  </button>
                  <button
                    onClick={() => setOutputFormat('ai')}
                    className={`flex-1 text-xs py-1.5 transition-colors ${
                      outputFormat === 'ai'
                        ? 'bg-brand-600 text-white'
                        : 'bg-gray-800 text-gray-400 hover:text-gray-200'
                    }`}
                  >
                    AI
                  </button>
                </div>
                <button
                  onClick={handleGenerate}
                  disabled={!sessionId || applying}
                  className='btn-primary text-xs py-1.5 w-full'
                >
                  {applying ? 'Generating…' : `Generate ${outputFormat.toUpperCase()}`}
                </button>
              </div>
              {isDone && sessionId && (
                <a
                  href={downloadUrl(sessionId)}
                  download
                  className='block text-center text-xs text-brand-400 hover:text-brand-300 transition-colors'
                >
                  ↓ Download {outputFormat.toUpperCase()}
                </a>
              )}
            </div>
            {/* UserForm */}
            <div className='flex-1 overflow-y-auto'>
              {loadingProfile ? (
                <p className='text-gray-500 text-sm p-4'>Loading profile…</p>
              ) : (
                <UserForm />
              )}
            </div>
          </div>

          {/* Right panel: PDF viewer */}
          <div className='flex-1 flex flex-col overflow-hidden bg-gray-950'>
            {sessionId ? (
              <>
                <PdfViewer
                  url={previewUrl(sessionId)}
                  page={currentPage}
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
                {pageCount > 1 && (
                  <div className='flex items-center justify-center gap-4 py-2 border-t border-gray-800'>
                    <button
                      onClick={() => setCurrentPage(Math.max(0, currentPage - 1))}
                      disabled={currentPage === 0}
                      className='text-xs text-gray-400 hover:text-gray-200 disabled:opacity-30'
                    >
                      ← Prev
                    </button>
                    <span className='text-xs text-gray-500'>
                      {currentPage + 1} / {pageCount}
                    </span>
                    <button
                      onClick={() => setCurrentPage(Math.min(pageCount - 1, currentPage + 1))}
                      disabled={currentPage === pageCount - 1}
                      className='text-xs text-gray-400 hover:text-gray-200 disabled:opacity-30'
                    >
                      Next →
                    </button>
                  </div>
                )}
              </>
            ) : (
              <div className='flex-1 flex items-center justify-center'>
                <p className='text-gray-600 text-sm'>Select a profile to load the PDF preview.</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
