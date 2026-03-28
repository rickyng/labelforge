import React from 'react'
import { Group, Label, Layer, Rect, Stage, Tag, Text } from 'react-konva'
import { useLabels } from '../context/LabelsContext'
import type { DocumentComponent } from '../types'

const COMPONENT_STYLE: Record<string, { stroke: string; fill: string; strokeWidth: number }> = {
  IMAGE:   { stroke: '#a855f7', fill: 'rgba(168,85,247,0.12)',  strokeWidth: 1 },
  BARCODE: { stroke: '#22c55e', fill: 'rgba(34,197,94,0.15)',   strokeWidth: 1.5 },
  SHAPE:   { stroke: '#9ca3af', fill: 'rgba(156,163,175,0.07)', strokeWidth: 1 },
}

interface AdminOverlayProps {
  canvasWidth: number
  canvasHeight: number
  pdfScale: number
  currentPage: number
  components?: DocumentComponent[]
}

export function AdminOverlay({ canvasWidth, canvasHeight, pdfScale, currentPage, components = [] }: AdminOverlayProps) {
  const {
    labels,
    updateLabel,
    selectedLabelId,
    setSelectedLabelId,
    hoveredLabelId,
    setHoveredLabelId,
    editableSet,
  } = useLabels()

  const pageLabels = labels.filter((l) => l.page === currentPage)
  const pageComponents = components.filter(
    (c) => c.page === currentPage && c.type !== 'TEXT'
  )

  return (
    <Stage
      width={canvasWidth}
      height={canvasHeight}
      style={{ position: 'absolute', top: 0, left: 0, pointerEvents: 'all' }}
    >
      {/* Component type overlay — rendered below labels layer */}
      <Layer listening={false}>
        {pageComponents.map((c) => {
          const [x0, y0, x1, y1] = c.bbox
          const style = COMPONENT_STYLE[c.type]
          if (!style) return null
          return (
            <Rect
              key={c.id}
              x={x0 * pdfScale}
              y={y0 * pdfScale}
              width={Math.max((x1 - x0) * pdfScale, 8)}
              height={Math.max((y1 - y0) * pdfScale, 8)}
              stroke={style.stroke}
              strokeWidth={style.strokeWidth}
              fill={style.fill}
              cornerRadius={2}
              listening={false}
            />
          )
        })}
      </Layer>
      <Layer>
        {pageLabels.map((lbl) => {
          const [x0, y0, x1, y1] = lbl.bbox
          const x = x0 * pdfScale
          const y = y0 * pdfScale
          const w = Math.max((x1 - x0) * pdfScale, 10)
          const h = Math.max((y1 - y0) * pdfScale, 10)

          const isHovered = lbl.id === hoveredLabelId
          const isSelected = lbl.id === selectedLabelId
          const isEditable = editableSet.has(lbl.id)
          const hasEdit = lbl.new_text !== null && lbl.new_text !== lbl.original_text

          const stroke = isHovered
            ? '#38bdf8'
            : isSelected
            ? '#818cf8'
            : hasEdit
            ? '#4ade80'
            : isEditable
            ? '#22c55e'
            : '#facc15'

          const fill = isHovered
            ? 'rgba(56,189,248,0.18)'
            : isSelected
            ? 'rgba(129,140,248,0.15)'
            : hasEdit
            ? 'rgba(74,222,128,0.12)'
            : isEditable
            ? 'rgba(34,197,94,0.08)'
            : 'rgba(250,204,21,0.06)'

          const strokeWidth = isHovered || isSelected ? 2.5 : 1.5
          const shadowBlur = isHovered ? 14 : isSelected ? 8 : 0
          const shadowColor = isHovered ? '#38bdf8' : '#818cf8'
          const tooltipText = `${lbl.id}\n${(lbl.new_text ?? lbl.original_text).slice(0, 32)}`

          return (
            <Group key={lbl.id}>
              <Rect
                x={x}
                y={y}
                width={w}
                height={h}
                stroke={stroke}
                strokeWidth={strokeWidth}
                fill={fill}
                shadowBlur={shadowBlur}
                shadowColor={shadowColor}
                draggable={isEditable}
                onClick={() => setSelectedLabelId(lbl.id)}
                onTap={() => setSelectedLabelId(lbl.id)}
                onMouseEnter={() => setHoveredLabelId(lbl.id)}
                onMouseLeave={() => setHoveredLabelId(null)}
                onDragEnd={(e) => {
                  const node = e.target
                  const nx = node.x() / pdfScale
                  const ny = node.y() / pdfScale
                  updateLabel(lbl.id, { bbox: [nx, ny, nx + (x1 - x0), ny + (y1 - y0)] })
                  node.x(nx * pdfScale)
                  node.y(ny * pdfScale)
                }}
              />
              <Text
                x={x + 2}
                y={y + 2}
                text={(lbl.new_text ?? lbl.original_text).slice(0, 20)}
                fontSize={Math.max(8, Math.min(lbl.fontsize * pdfScale, 13))}
                fill={isHovered ? '#7dd3fc' : isSelected ? '#c7d2fe' : hasEdit ? '#86efac' : isEditable ? '#bbf7d0' : '#fde047'}
                listening={false}
              />
              {isHovered && (
                <Label x={x} y={Math.max(0, y - 40)}>
                  <Tag
                    fill="#1e293b"
                    stroke="#38bdf8"
                    strokeWidth={1}
                    cornerRadius={4}
                    pointerDirection="down"
                    pointerWidth={8}
                    pointerHeight={6}
                  />
                  <Text
                    text={tooltipText}
                    fontSize={11}
                    fill="#e2e8f0"
                    padding={5}
                    listening={false}
                  />
                </Label>
              )}
            </Group>
          )
        })}
      </Layer>
    </Stage>
  )
}
