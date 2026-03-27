import React, { useRef, useEffect, useMemo } from 'react'
import { useLabels } from '../context/LabelsContext'

export function LabelTable() {
  const {
    labels,
    selectedLabelId,
    setSelectedLabelId,
    setCurrentPage,
    hoveredLabelId,
    setHoveredLabelId,
    editableSet,
    toggleEditable,
    searchQuery,
    setSearchQuery,
  } = useLabels()

  const rowRefs = useRef<Record<string, HTMLTableRowElement | null>>({})

  // Scroll hovered row into view when hover comes from overlay
  useEffect(() => {
    if (hoveredLabelId) {
      rowRefs.current[hoveredLabelId]?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    }
  }, [hoveredLabelId])

  if (labels.length === 0) {
    return (
      <div className="flex items-center justify-center h-40 text-gray-500 text-sm">
        No labels extracted yet.
      </div>
    )
  }

  const filtered = useMemo(() => {
    if (!searchQuery) return labels
    const q = searchQuery.toLowerCase()
    return labels.filter((l) =>
      l.original_text.toLowerCase().includes(q) ||
      String(l.page + 1).includes(q) ||
      l.id.toLowerCase().includes(q)
    )
  }, [labels, searchQuery])

  function handleRowClick(id: string, page: number) {
    setSelectedLabelId(id)
    setCurrentPage(page)
  }

  return (
    <div className="flex flex-col gap-2">
      {/* Search */}
      <input
        type="text"
        placeholder="Search labels…"
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
        className="input-field text-sm"
      />

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs text-left border-collapse">
          <thead>
            <tr className="border-b border-gray-200 text-gray-500">
              <th className="py-1.5 px-1">Editable</th>
              <th className="py-1.5 px-1">ID</th>
              <th className="py-1.5 px-1">Pg</th>
              <th className="py-1.5 px-1">Original Text</th>
              <th className="py-1.5 px-1">Sz</th>
              <th className="py-1.5 px-1">Color</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((lbl) => {
              const isHovered = lbl.id === hoveredLabelId
              const isSelected = lbl.id === selectedLabelId
              const isEditable = editableSet.has(lbl.id)

              const rowBg = isHovered
                ? 'bg-sky-50'
                : isSelected
                ? 'bg-indigo-50'
                : ''

              return (
                <tr
                  key={lbl.id}
                  ref={(el) => { rowRefs.current[lbl.id] = el }}
                  className={`border-b border-gray-100 cursor-pointer transition-colors ${rowBg} hover:bg-gray-50`}
                  onMouseEnter={() => setHoveredLabelId(lbl.id)}
                  onMouseLeave={() => setHoveredLabelId(null)}
                  onClick={() => handleRowClick(lbl.id, lbl.page)}
                >
                  {/* Make Editable toggle */}
                  <td className="py-1 px-1" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={isEditable}
                      onChange={() => toggleEditable(lbl.id)}
                      className="accent-green-500"
                      title="Make editable for users"
                    />
                  </td>

                  {/* ID */}
                  <td className="py-1 px-1 font-mono text-gray-400 max-w-[60px] truncate" title={lbl.id}>
                    {lbl.id.slice(0, 8)}
                  </td>

                  {/* Page */}
                  <td className="py-1 px-1 text-gray-500">{lbl.page + 1}</td>

                  {/* Original Text */}
                  <td className="py-1 px-1 max-w-[160px] truncate text-gray-700" title={lbl.original_text}>
                    {lbl.original_text || <em className="text-gray-600">empty</em>}
                  </td>

                  {/* Font Size (read-only) */}
                  <td className="py-1 px-1 text-gray-500 tabular-nums">{lbl.fontsize.toFixed(1)}</td>

                  {/* Color (read-only swatch) */}
                  <td className="py-1 px-1">
                    <span
                      className="inline-block w-4 h-4 rounded-sm border border-gray-300"
                      style={{ background: lbl.color ?? '#000000' }}
                      title={lbl.color ?? '#000000'}
                    />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>

        {filtered.length === 0 && searchQuery && (
          <div className="text-center text-gray-400 text-xs py-4">No matches for "{searchQuery}"</div>
        )}
      </div>
    </div>
  )
}
