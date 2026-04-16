import React, { useEffect, useMemo, useRef, useState } from 'react'
import { useLabels } from '../context/LabelsContext'
import type { ComponentType, DocumentComponent, Label } from '../types'

type TableRow = { kind: 'label'; data: Label } | { kind: 'component'; data: DocumentComponent }

interface LabelTableProps {
  changesForSize?: Record<string, string>
  components?: DocumentComponent[]
}

export function LabelTable({ changesForSize = {}, components = [] }: LabelTableProps) {
  const {
    labels,
    selectedLabelId,
    setSelectedLabelId,
    setCurrentPage,
    hoveredLabelId,
    setHoveredLabelId,
    searchQuery,
    setSearchQuery,
  } = useLabels()

  const [typeFilter, setTypeFilter] = useState<ComponentType | 'ALL'>('TEXT')
  const rowRefs = useRef<Record<string, HTMLTableRowElement | null>>({})

  const rows: TableRow[] = useMemo(() => {
    if (typeFilter === 'ALL') {
      const r: TableRow[] = labels.map(l => ({ kind: 'label' as const, data: l }))
      r.push(...components.map(c => ({ kind: 'component' as const, data: c })))
      return r
    }
    if (typeFilter === 'TEXT') {
      return labels.map(l => ({ kind: 'label' as const, data: l }))
    }
    return components
      .filter(c => c.type === typeFilter)
      .map(c => ({ kind: 'component' as const, data: c }))
  }, [labels, components, typeFilter])

  const filtered = useMemo(() => {
    if (!searchQuery) return rows
    const q = searchQuery.toLowerCase()
    return rows.filter((row) => {
      const id = row.data.id
      const page = row.data.page
      if (id.toLowerCase().includes(q) || String(page + 1).includes(q)) return true
      if (row.kind === 'label' && row.data.original_text.toLowerCase().includes(q)) return true
      return false
    })
  }, [rows, searchQuery])

  useEffect(() => {
    if (hoveredLabelId) {
      rowRefs.current[hoveredLabelId]?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    }
  }, [hoveredLabelId])

  function handleRowClick(id: string, page: number) {
    setSelectedLabelId(id)
    setCurrentPage(page)
  }

  function typeBadge(type: string) {
    const colors: Record<string, string> = {
      TEXT: 'bg-blue-100 text-blue-700',
      SHAPE: 'bg-gray-100 text-gray-700',
      IMAGE: 'bg-purple-100 text-purple-700',
      BARCODE: 'bg-green-100 text-green-700',
    }
    return colors[type] ?? 'bg-gray-100 text-gray-600'
  }

  const nothing = rows.length === 0

  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-2">
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value as ComponentType | 'ALL')}
          className="border rounded px-2 py-1 text-sm shrink-0"
        >
          <option value="ALL">All</option>
          <option value="TEXT">TEXT</option>
          <option value="SHAPE">SHAPE</option>
          <option value="IMAGE">IMAGE</option>
          <option value="BARCODE">BARCODE</option>
        </select>
        <input
          type="text"
          placeholder="Search…"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="input-field text-sm flex-1"
        />
      </div>

      {nothing ? (
        <div className="flex items-center justify-center h-20 text-gray-400 text-xs">
          Select a template to see components.
        </div>
      ) : (
      <div className="overflow-x-auto">
        <table className="w-full text-xs text-left border-collapse">
          <thead>
            <tr className="border-b border-gray-200 text-gray-500">
              <th className="py-1 px-1">ID</th>
              <th className="py-1 px-1">Pg</th>
              {typeFilter === 'ALL' && <th className="py-1 px-1">Type</th>}
              {typeFilter === 'ALL' && <th className="py-1 px-1">Summary</th>}
              {typeFilter === 'TEXT' && <th className="py-1 px-1">Original Text</th>}
              {typeFilter === 'TEXT' && <th className="py-1 px-1">Intended</th>}
              {typeFilter === 'TEXT' && <th className="py-1 px-1">Sz</th>}
              {typeFilter === 'TEXT' && <th className="py-1 px-1">Color</th>}
              {typeFilter === 'SHAPE' && <th className="py-1 px-1">Fill Color</th>}
              {typeFilter === 'SHAPE' && <th className="py-1 px-1">Opacity</th>}
              {typeFilter === 'SHAPE' && <th className="py-1 px-1">OCR Text</th>}
              {typeFilter === 'SHAPE' && <th className="py-1 px-1">OCR Conf</th>}
              {typeFilter === 'IMAGE' && <th className="py-1 px-1">Format</th>}
              {typeFilter === 'IMAGE' && <th className="py-1 px-1">Dimensions</th>}
              {typeFilter === 'BARCODE' && <th className="py-1 px-1">Value</th>}
              {typeFilter === 'BARCODE' && <th className="py-1 px-1">Format</th>}
            </tr>
          </thead>
          <tbody>
            {filtered.map((row) => {
              const id = row.data.id
              const page = row.data.page
              const isHovered = id === hoveredLabelId
              const isSelected = id === selectedLabelId

              const rowBg = isHovered
                ? 'bg-sky-50'
                : isSelected
                ? 'bg-indigo-50'
                : ''

              return (
                <tr
                  key={id}
                  ref={(el) => { rowRefs.current[id] = el }}
                  className={`border-b border-gray-100 cursor-pointer transition-colors ${rowBg} hover:bg-gray-50`}
                  onMouseEnter={() => setHoveredLabelId(id)}
                  onMouseLeave={() => setHoveredLabelId(null)}
                  onClick={() => handleRowClick(id, page)}
                >
                  <td className="py-1 px-1 font-mono text-gray-400 max-w-[120px] truncate" title={id}>
                    {id.slice(0, 16)}
                  </td>
                  <td className="py-1 px-1 text-gray-500">{page + 1}</td>

                  {typeFilter === 'ALL' && (
                    <td className="py-1 px-1">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${typeBadge(row.kind === 'label' ? 'TEXT' : row.data.type)}`}>
                        {row.kind === 'label' ? 'TEXT' : row.data.type}
                      </span>
                    </td>
                  )}
                  {typeFilter === 'ALL' && (
                    <td className="py-1 px-1 max-w-[140px] truncate text-gray-600">
                      {row.kind === 'label'
                        ? row.data.original_text || <em className="text-gray-400">empty</em>
                        : row.data.type === 'SHAPE'
                        ? row.data.fill_color ?? '—'
                        : row.data.type === 'IMAGE'
                        ? `${row.data.width_px ?? '?'}x${row.data.height_px ?? '?'}`
                        : row.data.barcode_value ?? '—'
                      }
                    </td>
                  )}

                  {typeFilter === 'TEXT' && (
                    <>
                      <td className="py-1 px-1 max-w-[140px] truncate text-gray-700" title={row.kind === 'label' ? row.data.original_text : undefined}>
                        {row.kind === 'label'
                          ? (row.data.original_text || <em className="text-gray-400">empty</em>)
                          : '—'
                        }
                      </td>
                      <td className="py-1 px-1 max-w-[120px] truncate">
                        {(() => {
                          if (row.kind !== 'label') return <span className="text-gray-300">—</span>
                          const v = changesForSize[id]
                          return v !== undefined
                            ? <span className="text-green-700 font-medium">{v}</span>
                            : <span className="text-gray-300">—</span>
                        })()}
                      </td>
                      <td className="py-1 px-1 text-gray-500 tabular-nums">
                        {row.kind === 'label' ? row.data.fontsize.toFixed(1) : '—'}
                      </td>
                      <td className="py-1 px-1">
                        <span
                          className="inline-block w-3.5 h-3.5 rounded-sm border border-gray-300"
                          style={{ background: row.kind === 'label' ? (row.data.color ?? '#000') : '#000' }}
                          title={row.kind === 'label' ? (row.data.color ?? '#000') : '#000'}
                        />
                      </td>
                    </>
                  )}

                  {typeFilter === 'SHAPE' && row.kind === 'component' && (
                    <>
                      <td className="py-1 px-1">
                        {row.data.fill_color ? (
                          <span className="flex items-center gap-1">
                            <span
                              className="inline-block w-3.5 h-3.5 rounded-sm border border-gray-300"
                              style={{ background: row.data.fill_color }}
                            />
                            <span className="text-gray-600">{row.data.fill_color}</span>
                          </span>
                        ) : <span className="text-gray-300">none</span>}
                      </td>
                      <td className="py-1 px-1 text-gray-500">
                        {row.data.fill_opacity != null ? row.data.fill_opacity.toFixed(2) : '—'}
                      </td>
                      <td className="py-1 px-1 max-w-[140px] truncate text-gray-700" title={row.data.ocr_text ?? undefined}>
                        {row.data.ocr_text
                          ? <span className="text-blue-700">{row.data.ocr_text}</span>
                          : <span className="text-gray-300">—</span>
                        }
                      </td>
                      <td className="py-1 px-1">
                        {row.data.ocr_confidence != null ? (
                          <span className={row.data.ocr_confidence > 0.8 ? 'text-green-600' : 'text-yellow-600'}>
                            {(row.data.ocr_confidence * 100).toFixed(0)}%
                          </span>
                        ) : <span className="text-gray-300">—</span>}
                      </td>
                    </>
                  )}

                  {typeFilter === 'IMAGE' && row.kind === 'component' && (
                    <>
                      <td className="py-1 px-1 text-gray-500">{row.data.image_format ?? '—'}</td>
                      <td className="py-1 px-1 text-gray-500">
                        {row.data.width_px ? `${row.data.width_px}x${row.data.height_px}` : '—'}
                      </td>
                    </>
                  )}

                  {typeFilter === 'BARCODE' && row.kind === 'component' && (
                    <>
                      <td className="py-1 px-1 text-gray-500 max-w-[100px] truncate">
                        {row.data.barcode_value ?? '—'}
                      </td>
                      <td className="py-1 px-1 text-gray-500">
                        {row.data.barcode_format ?? '—'}
                      </td>
                    </>
                  )}
                </tr>
              )
            })}
          </tbody>
        </table>

        {filtered.length === 0 && (
          <div className="text-center text-gray-400 text-xs py-3">
            {searchQuery ? `No matches for "${searchQuery}"` : `No ${typeFilter === 'ALL' ? 'components' : typeFilter} found`}
          </div>
        )}
      </div>
      )}
    </div>
  )
}
