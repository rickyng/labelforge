import { useMemo, useCallback, useRef, useState } from 'react'
import type { ResolvedField } from '../types'

interface Props {
  fields: ResolvedField[]
  sizeIndex: number
}

const DEFAULT_WIDTHS = [10, 30, 35, 25] // ID, PDF Field, JSON Path, Value

export function FieldMappingTable({ fields, sizeIndex }: Props) {
  const rows = useMemo(() => {
    if (!fields?.length) return []
    return fields
      .filter(f => f.field_type !== 'unmapped')
      .sort((a, b) => a.id.localeCompare(b.id))
  }, [fields])

  const [widths, setWidths] = useState(DEFAULT_WIDTHS)
  const containerRef = useRef<HTMLDivElement>(null)
  const dragging = useRef<{ col: number; startX: number; startWidths: number[] } | null>(null)

  const onResizeStart = useCallback((col: number, e: React.MouseEvent) => {
    e.preventDefault()
    dragging.current = { col, startX: e.clientX, startWidths: [...widths] }

    const onMove = (ev: MouseEvent) => {
      if (!dragging.current || !containerRef.current) return
      const containerWidth = containerRef.current.clientWidth
      const dx = ev.clientX - dragging.current.startX
      const pctDelta = (dx / containerWidth) * 100
      const c = dragging.current.col
      const next = c + 1
      if (next >= widths.length) return
      const newWidths = [...dragging.current.startWidths]
      newWidths[c] = Math.max(5, newWidths[c] + pctDelta)
      newWidths[next] = Math.max(5, newWidths[next] - pctDelta)
      setWidths(newWidths)
    }

    const onUp = () => {
      dragging.current = null
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }

    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }, [widths])

  if (rows.length === 0) return null

  const colStyle = (i: number) => ({ width: `${widths[i]}%`, minWidth: 0 })

  return (
    <div ref={containerRef} className="border rounded bg-gray-50 max-h-48 overflow-y-auto">
      <table className="w-full text-xs table-fixed">
        <thead className="sticky top-0 bg-gray-100 z-10">
          <tr className="border-b text-gray-500">
            <th style={colStyle(0)} className="py-1 px-2 text-left font-medium relative group">
              ID
              <span
                className="absolute right-0 top-0 bottom-0 w-1.5 cursor-col-resize hover:bg-gray-300 active:bg-gray-400 z-10"
                onMouseDown={(e) => onResizeStart(0, e)}
              />
            </th>
            <th style={colStyle(1)} className="py-1 px-2 text-left font-medium relative group">
              PDF Field
              <span
                className="absolute right-0 top-0 bottom-0 w-1.5 cursor-col-resize hover:bg-gray-300 active:bg-gray-400 z-10"
                onMouseDown={(e) => onResizeStart(1, e)}
              />
            </th>
            <th style={colStyle(2)} className="py-1 px-2 text-left font-medium relative group">
              JSON Path
              <span
                className="absolute right-0 top-0 bottom-0 w-1.5 cursor-col-resize hover:bg-gray-300 active:bg-gray-400 z-10"
                onMouseDown={(e) => onResizeStart(2, e)}
              />
            </th>
            <th style={colStyle(3)} className="py-1 px-2 text-left font-medium">
              Value
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((field) => {
            // single fields have 1 value; per_size fields have one per size
            const value = field.field_type === 'per_size'
              ? field.values[sizeIndex]
              : field.values[0]
            return (
              <tr key={field.id} className="border-b border-gray-100 last:border-0">
                <td style={colStyle(0)} className="py-0.5 px-2 font-mono text-gray-400 truncate" title={field.id}>
                  {field.id}
                </td>
                <td style={colStyle(1)} className="py-0.5 px-2 font-mono text-gray-600 truncate" title={field.pdf_reference}>
                  {field.pdf_reference}
                </td>
                <td style={colStyle(2)} className="py-0.5 px-2 font-mono text-blue-600 truncate" title={field.json_path}>
                  {field.json_path || <span className="text-gray-300">&mdash;</span>}
                </td>
                <td style={colStyle(3)} className="py-0.5 px-2 font-mono text-gray-900 truncate" title={value ?? undefined}>
                  {value || <span className="text-gray-300">&mdash;</span>}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
