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
  const [saving, setSaving] = useState(false)
  const [canvasSize, setCanvasSize] = useState({ w: 800, h: 1000, scale: 1 })
  const [previewing, setPreviewing] = useState(false)
  const [previewMode, setPreviewMode] = useState(false)
  const [previewKey, setPreviewKey] = useState(0)

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

  const refreshPreview = useCallback(async () => {
    if (!sessionId) return
    setPreviewing(true)
    try {
      const toApply = editableLabels.filter((l) => l.new_text !== null)
      await applyLabels(sessionId, toApply, 'pdf')
      setIsDone(true)
      setPreviewKey((k) => k + 1)
    } catch (err) {
      addToast(String(err), 'error')
    } finally {
      setPreviewing(false)
    }
  }, [sessionId, editableLabels, addToast, setIsDone])

  const handlePreview = useCallback(async () => {
    await refreshPreview()
    setPreviewMode(true)
  }, [refreshPreview])


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

  const isEditorOpen = activeLabel !== null


  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Top bar */}
      <header className="flex items-center justify-between px-5 py-3 border-b border-gray-200 bg-white shadow-sm">
        <div className="flex items-center gap-2.5">
          <span className="text-lg">🏷️</span>
          <span className="font-bold text-gray-900 tracking-tight">LabelForge</span>
        </div>
        <div className="flex items-center gap-2">
          {isEditorOpen && (
            <button onClick={handleBackToList} className="btn-ghost">
              ← Labels
            </button>
          )}
          <button onClick={handleLogout} className="btn-ghost">Logout</button>
        </div>
      </header>

      {/* LIST VIEW */}
      {!isEditorOpen && (
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-2xl mx-auto px-4 py-10 space-y-5">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">My Labels</h2>
                <p className="text-xs text-gray-500 mt-0.5">Saved text-replacement sets</p>
              </div>
              <button onClick={openNewEditor} className="btn-primary text-sm py-1.5 px-4 flex items-center gap-1.5">
                <span className="text-base leading-none">+</span> New Label
              </button>
            </div>
            {loadingList ? (
              <div className="flex items-center gap-2 text-gray-600 text-sm py-6">
                <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                </svg>
                Loading…
              </div>
            ) : userLabels.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 gap-3 text-gray-600">
                <svg className="w-10 h-10 opacity-40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                </svg>
                <p className="text-sm">No labels yet</p>
                <button onClick={openNewEditor} className="btn-primary text-sm py-1.5 px-4 mt-1">Create your first label</button>
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {userLabels.map((ul) => (
                  <div
                    key={ul.name}
                    className="group flex items-center justify-between gap-3 rounded-xl border border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50 px-4 py-3.5 transition-all duration-150 cursor-pointer shadow-sm"
                    onClick={() => openExistingEditor(ul)}
                  >
                    <div className="min-w-0">
                      <div className="font-semibold text-gray-900 text-sm truncate">{ul.name}</div>
                      <div className="text-xs text-gray-500 mt-0.5">
                        <span className="text-gray-500">{ul.profile_name}</span>
                        <span className="mx-1.5 text-gray-300">·</span>
                        {new Date(ul.updated_at).toLocaleDateString()}
                      </div>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        onClick={(e) => { e.stopPropagation(); openExistingEditor(ul) }}
                        className="opacity-0 group-hover:opacity-100 btn-ghost text-brand-400 hover:text-brand-300"
                      >
                        Edit
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDeleteLabel(ul.name) }}
                        className="opacity-0 group-hover:opacity-100 btn-ghost text-gray-600 hover:text-red-400"
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
          <div className='w-80 shrink-0 flex flex-col border-r border-gray-200 bg-white overflow-hidden'>
            {/* Panel header */}
            <div className='px-4 py-3 border-b border-gray-200 flex items-center gap-2'>
              <button
                onClick={handleBackToList}
                className='btn-ghost p-1.5 -ml-1 text-gray-500'
                title='Back to labels'
              >
                <svg className='w-4 h-4' fill='none' viewBox='0 0 24 24' stroke='currentColor'>
                  <path strokeLinecap='round' strokeLinejoin='round' strokeWidth={2} d='M15 19l-7-7 7-7' />
                </svg>
              </button>
              <span className='text-sm font-semibold text-gray-900 truncate'>
                {activeLabel || 'New Label'}
              </span>
            </div>

            {/* Controls */}
            <div className='p-4 space-y-4 border-b border-gray-200 shrink-0'>
              {/* Profile */}
              <div className='space-y-1.5'>
                <label className='label-tag'>Profile</label>
                <select
                  value={selectedProfile}
                  onChange={(e) => handleProfileChange(e.target.value)}
                  disabled={loadingProfile}
                  className='input-field'
                >
                  <option value=''>— select profile —</option>
                  {profiles.map((p) => (
                    <option key={p.name} value={p.name}>{p.name}</option>
                  ))}
                </select>
              </div>
              {/* Label name */}
              <div className='space-y-1.5'>
                <label className='label-tag'>Label name</label>
                <input
                  type='text'
                  value={labelName}
                  onChange={(e) => setLabelName(e.target.value)}
                  placeholder='e.g. Client X'
                  className='input-field'
                />
              </div>
              {/* Save */}
              <button
                onClick={handleSaveLabel}
                disabled={saving}
                className='btn-secondary text-sm py-2 w-full'
              >
                {saving ? 'Saving…' : 'Save Label'}
              </button>
            </div>

            {/* Fields list */}
            <div className='flex-1 overflow-y-auto'>
              {loadingProfile ? (
                <div className='flex items-center gap-2 text-gray-600 text-sm p-4'>
                  <svg className='animate-spin w-4 h-4' viewBox='0 0 24 24' fill='none'>
                    <circle className='opacity-25' cx='12' cy='12' r='10' stroke='currentColor' strokeWidth='4'/>
                    <path className='opacity-75' fill='currentColor' d='M4 12a8 8 0 018-8v8z'/>
                  </svg>
                  Loading profile…
                </div>
              ) : (
                <UserForm onFieldBlur={previewMode ? refreshPreview : undefined} />
              )}
            </div>
          </div>

          {/* Right panel */}
          <div className='flex-1 flex flex-col overflow-hidden bg-gray-50'>
            {/* Tab bar */}
            {sessionId && (
              <div className='flex border-b border-gray-200 bg-white shrink-0'>
                <button
                  onClick={() => setPreviewMode(false)}
                  className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors ${
                    !previewMode
                      ? 'border-brand-500 text-gray-900'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  Original
                </button>
                <button
                  onClick={() => { if (isDone) setPreviewMode(true); else handlePreview() }}
                  className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors ${
                    previewMode
                      ? 'border-brand-500 text-gray-900'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  {previewing ? 'Generating…' : 'Preview'}
                </button>
              </div>
            )}
            {sessionId ? (
              previewMode ? (
                <PdfViewer
                  url={`${downloadUrl(sessionId)}?v=${previewKey}`}
                  page={currentPage}
                  onDimensions={handleDimensions}
                />
              ) : (
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
                    <div className='flex items-center justify-center gap-4 py-2.5 border-t border-gray-200 bg-white'>
                      <button
                        onClick={() => setCurrentPage(Math.max(0, currentPage - 1))}
                        disabled={currentPage === 0}
                        className='btn-ghost py-1 px-2 disabled:opacity-30'
                      >
                        ← Prev
                      </button>
                      <span className='text-xs font-medium text-gray-500'>
                        {currentPage + 1} <span className='text-gray-300'>/</span> {pageCount}
                      </span>
                      <button
                        onClick={() => setCurrentPage(Math.min(pageCount - 1, currentPage + 1))}
                        disabled={currentPage === pageCount - 1}
                        className='btn-ghost py-1 px-2 disabled:opacity-30'
                      >
                        Next →
                      </button>
                    </div>
                  )}
                </>
              )
            ) : (
              <div className='flex-1 flex flex-col items-center justify-center gap-3 text-gray-600'>
                <svg className='w-12 h-12 opacity-30' fill='none' viewBox='0 0 24 24' stroke='currentColor'>
                  <path strokeLinecap='round' strokeLinejoin='round' strokeWidth={1} d='M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' />
                </svg>
                <p className='text-sm'>Select a profile to preview the PDF</p>
              </div>
            )}
          </div>
        </div>
      )}

    </div>
  )
}
