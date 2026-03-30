import { useCallback, useEffect, useRef, useState } from 'react'

interface ResizablePanelProps {
  defaultWidth: number
  minWidth?: number
  maxWidth?: number
  side?: 'left' | 'right'
  className?: string
  children: React.ReactNode
}

export function ResizablePanel({
  defaultWidth,
  minWidth = 160,
  maxWidth = 600,
  side = 'left',
  className = '',
  children,
}: ResizablePanelProps) {
  const [width, setWidth] = useState(defaultWidth)
  const dragging = useRef(false)
  const startX = useRef(0)
  const startWidth = useRef(0)

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    dragging.current = true
    startX.current = e.clientX
    startWidth.current = width
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
  }, [width])

  useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      if (!dragging.current) return
      const delta = side === 'left'
        ? e.clientX - startX.current
        : startX.current - e.clientX
      const next = Math.min(maxWidth, Math.max(minWidth, startWidth.current + delta))
      setWidth(next)
    }
    const onMouseUp = () => {
      if (!dragging.current) return
      dragging.current = false
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
    return () => {
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }
  }, [side, minWidth, maxWidth])

  const handle = (
    <div
      onMouseDown={onMouseDown}
      className="absolute top-0 bottom-0 w-1 cursor-col-resize z-10 hover:bg-brand-300 active:bg-brand-400 transition-colors"
      style={{ [side === 'left' ? 'right' : 'left']: -2 }}
    />
  )

  return (
    <div
      className={`relative shrink-0 ${className}`}
      style={{ width }}
    >
      {children}
      {handle}
    </div>
  )
}
