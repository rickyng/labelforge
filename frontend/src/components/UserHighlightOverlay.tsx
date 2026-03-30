import React from 'react'
import { Layer, Rect, Stage } from 'react-konva'
import type { Label } from '../types'

interface UserHighlightOverlayProps {
  canvasWidth: number
  canvasHeight: number
  pdfScale: number
  currentPage: number
  labels: Label[]
  highlightedIds: Set<string>
  hoveredLabelId: string | null
  onHoverChange: (id: string | null) => void
}

export function UserHighlightOverlay({
  canvasWidth,
  canvasHeight,
  pdfScale,
  currentPage,
  labels,
  highlightedIds,
  hoveredLabelId,
  onHoverChange,
}: UserHighlightOverlayProps) {
  const pageLabels = labels.filter(
    (l) => l.page === currentPage && highlightedIds.has(l.id)
  )

  return (
    <Stage
      width={canvasWidth}
      height={canvasHeight}
      style={{ position: 'absolute', top: 0, left: 0, pointerEvents: 'all' }}
    >
      <Layer>
        {pageLabels.map((lbl) => {
          const [x0, y0, x1, y1] = lbl.bbox
          const isHovered = hoveredLabelId === lbl.id
          return (
            <Rect
              key={lbl.id}
              x={x0 * pdfScale}
              y={y0 * pdfScale}
              width={Math.max((x1 - x0) * pdfScale, 6)}
              height={Math.max((y1 - y0) * pdfScale, 6)}
              stroke={isHovered ? '#d97706' : '#f59e0b'}
              strokeWidth={isHovered ? 2.5 : 1.5}
              fill={isHovered ? 'rgba(217,119,6,0.28)' : 'rgba(245,158,11,0.18)'}
              cornerRadius={2}
              onMouseEnter={() => onHoverChange(lbl.id)}
              onMouseLeave={() => onHoverChange(null)}
            />
          )
        })}
      </Layer>
    </Stage>
  )
}
