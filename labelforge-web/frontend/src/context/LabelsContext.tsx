import React, { createContext, useCallback, useContext, useMemo, useState } from 'react'
import type { Label } from '../types'

interface LabelsContextValue {
  labels: Label[]
  setLabels: (labels: Label[]) => void
  updateLabel: (id: string, patch: Partial<Label>) => void
  resetLabel: (id: string) => void
  sessionId: string | null
  setSessionId: (id: string | null) => void
  pageCount: number
  setPageCount: (n: number) => void
  currentPage: number
  setCurrentPage: (n: number) => void
  selectedLabelId: string | null
  setSelectedLabelId: (id: string | null) => void
  isDone: boolean
  setIsDone: (v: boolean) => void
  // Hover sync
  hoveredLabelId: string | null
  setHoveredLabelId: (id: string | null) => void
  // Editable set
  editableSet: Set<string>
  toggleEditable: (id: string) => void
  setAllEditable: (ids: string[], value: boolean) => void
  loadEditableIds: (ids: string[]) => void
  editableLabels: Label[]
  // Bulk row selection
  selectedRows: Set<string>
  toggleSelected: (id: string) => void
  selectAll: (ids: string[]) => void
  clearSelected: () => void
  // Search
  searchQuery: string
  setSearchQuery: (q: string) => void
}

const LabelsContext = createContext<LabelsContextValue | null>(null)

export function LabelsProvider({ children }: { children: React.ReactNode }) {
  const [labels, setLabelsState] = useState<Label[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [pageCount, setPageCount] = useState(0)
  const [currentPage, setCurrentPage] = useState(0)
  const [selectedLabelId, setSelectedLabelId] = useState<string | null>(null)
  const [isDone, setIsDone] = useState(false)
  const [hoveredLabelId, setHoveredLabelId] = useState<string | null>(null)
  const [editableSet, setEditableSet] = useState<Set<string>>(new Set())
  const [selectedRows, setSelectedRows] = useState<Set<string>>(new Set())
  const [searchQuery, setSearchQuery] = useState('')

  const setLabels = useCallback((next: Label[]) => {
    setLabelsState(next)
    setIsDone(false)
    setEditableSet(new Set())
    setSelectedRows(new Set())
    setSearchQuery('')
  }, [])

  const updateLabel = useCallback((id: string, patch: Partial<Label>) => {
    setLabelsState((prev) =>
      prev.map((lbl) => (lbl.id === id ? { ...lbl, ...patch } : lbl)),
    )
  }, [])

  const resetLabel = useCallback((id: string) => {
    setLabelsState((prev) =>
      prev.map((lbl) => (lbl.id === id ? { ...lbl, new_text: null } : lbl)),
    )
  }, [])

  const toggleEditable = useCallback((id: string) => {
    setEditableSet((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }, [])

  const setAllEditable = useCallback((ids: string[], value: boolean) => {
    setEditableSet((prev) => {
      const next = new Set(prev)
      ids.forEach((id) => (value ? next.add(id) : next.delete(id)))
      return next
    })
  }, [])

  const loadEditableIds = useCallback((ids: string[]) => {
    setEditableSet(new Set(ids))
  }, [])

  const toggleSelected = useCallback((id: string) => {
    setSelectedRows((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }, [])

  const selectAll = useCallback((ids: string[]) => {
    setSelectedRows(new Set(ids))
  }, [])

  const clearSelected = useCallback(() => setSelectedRows(new Set()), [])

  const editableLabels = useMemo(
    () => labels.filter((l) => editableSet.has(l.id)),
    [labels, editableSet],
  )

  return (
    <LabelsContext.Provider
      value={{
        labels,
        setLabels,
        updateLabel,
        resetLabel,
        sessionId,
        setSessionId,
        pageCount,
        setPageCount,
        currentPage,
        setCurrentPage,
        selectedLabelId,
        setSelectedLabelId,
        isDone,
        setIsDone,
        hoveredLabelId,
        setHoveredLabelId,
        editableSet,
        toggleEditable,
        setAllEditable,
        loadEditableIds,
        editableLabels,
        selectedRows,
        toggleSelected,
        selectAll,
        clearSelected,
        searchQuery,
        setSearchQuery,
      }}
    >
      {children}
    </LabelsContext.Provider>
  )
}

export function useLabels(): LabelsContextValue {
  const ctx = useContext(LabelsContext)
  if (!ctx) throw new Error('useLabels must be used within LabelsProvider')
  return ctx
}
