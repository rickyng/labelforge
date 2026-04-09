import React from 'react'

const round = (z: number) => Math.round(z * 100) / 100

interface ZoomControlsProps {
  zoom: number
  onZoomChange: (zoom: number) => void
  step?: number
  min?: number
  max?: number
  className?: string
  btnClassName?: string
}

export function ZoomControls({
  zoom,
  onZoomChange,
  step = 0.25,
  min = 0.5,
  max = 4,
  className = '',
  btnClassName = '',
}: ZoomControlsProps) {
  return (
    <div className={`flex items-center gap-1 ${className}`}>
      <button
        onClick={() => onZoomChange(round(zoom - step))}
        disabled={zoom <= min}
        className={`disabled:opacity-30 ${btnClassName}`}
        title="Zoom out"
      >−</button>
      <span className="text-xs text-gray-400 w-10 text-center">{Math.round(zoom * 100)}%</span>
      <button
        onClick={() => onZoomChange(round(zoom + step))}
        disabled={zoom >= max}
        className={`disabled:opacity-30 ${btnClassName}`}
        title="Zoom in"
      >+</button>
      <button
        onClick={() => onZoomChange(1)}
        disabled={zoom === 1}
        className={`disabled:opacity-30 ${btnClassName}`}
        title="Reset zoom"
      >Reset</button>
    </div>
  )
}
