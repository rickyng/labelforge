import React from 'react'
import { Group, Label, Layer, Rect, Stage, Tag, Text } from 'react-konva'
import { useLabels } from '../context/LabelsContext'
import type { DocumentComponent } from '../types'

const COMPONENT_STYLE: Record<string, { stroke: string; strokeWidth: number }> = {
  IMAGE:   { stroke: '#a855f7', strokeWidth: 1 },
  BARCODE: { stroke: '#22c55e', strokeWidth: 1.5 },
  SHAPE:   { stroke: '#9ca3af', strokeWidth: 1 },
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
      {/* Component type overlay — interactive (hover, click, tooltip) */}
      <Layer>
        {pageComponents.map((c) => {
          const [x0, y0, x1, y1] = c.bbox
          const style = COMPONENT_STYLE[c.type]
          if (!style) return null

          const x = x0 * pdfScale
          const y = y0 * pdfScale
          const w = Math.max((x1 - x0) * pdfScale, 8)
          const h = Math.max((y1 - y0) * pdfScale, 8)

          const isHovered = c.id === hoveredLabelId
          const isSelected = c.id === selectedLabelId
          const isEditable = editableSet.has(c.id)

          const stroke = isHovered
            ? '#38bdf8'
            : isSelected
            ? '#818cf8'
            : isEditable
            ? '#22c55e'
            : style.stroke

          const strokeWidth = isHovered || isSelected ? 2.5 : style.strokeWidth

          let tooltipText = `${c.id}\n${c.type}`
          if (c.type === 'SHAPE') {
            if (c.ocr_text) {
              tooltipText += `\nOCR: "${c.ocr_text}" (${c.ocr_confidence != null ? (c.ocr_confidence * 100).toFixed(0) + '%' : '?'})`
            }
            if (c.fill_color) {
              tooltipText += `\nfill: ${c.fill_color}`
            }
          } else if (c.type === 'BARCODE' && c.barcode_value) {
            tooltipText += `\nvalue: ${c.barcode_value}`
          } else if (c.type === 'IMAGE') {
            tooltipText += `\n${c.width_px ?? '?'}x${c.height_px ?? '?'}`
          }

          return (
            <Group key={c.id}>
              <Rect
                x={x}
                y={y}
                width={w}
                height={h}
                stroke={stroke}
                strokeWidth={strokeWidth}
                cornerRadius={2}
                onClick={() => setSelectedLabelId(c.id)}
                onTap={() => setSelectedLabelId(c.id)}
                onMouseEnter={() => setHoveredLabelId(c.id)}
                onMouseLeave={() => setHoveredLabelId(null)}
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
      {/* TEXT label overlay — interactive with drag support */}
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

          const strokeWidth = isHovered || isSelected ? 2.5 : 1.5
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
