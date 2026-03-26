import React, { useCallback, useEffect, useRef, useState } from 'react'

// PDF.js loaded from CDN via dynamic import
let pdfjsLib: typeof import('pdfjs-dist') | null = null

async function getPdfjs() {
  if (!pdfjsLib) {
    pdfjsLib = await import('pdfjs-dist')
    pdfjsLib.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.mjs`
  }
  return pdfjsLib
}

interface PdfViewerProps {
  url: string
  page: number // 0-based
  onPageCount?: (n: number) => void
  onDimensions?: (w: number, h: number, scale: number) => void
  overlay?: React.ReactNode
}

export function PdfViewer({ url, page, onPageCount, onDimensions, overlay }: PdfViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const pdfRef = useRef<import('pdfjs-dist').PDFDocumentProxy | null>(null)

  const renderPage = useCallback(async () => {
    const doc = pdfRef.current
    if (!doc || !canvasRef.current) return
    setLoading(true)
    try {
      const pdfPage = await doc.getPage(page + 1) // PDF.js is 1-based
      const container = containerRef.current
      const containerWidth = container?.clientWidth ?? 800
      const viewport = pdfPage.getViewport({ scale: 1 })
      const scale = containerWidth / viewport.width
      const scaledViewport = pdfPage.getViewport({ scale })

      const canvas = canvasRef.current
      canvas.width = scaledViewport.width
      canvas.height = scaledViewport.height

      const ctx = canvas.getContext('2d')!
      await pdfPage.render({ canvasContext: ctx, viewport: scaledViewport }).promise
      onDimensions?.(scaledViewport.width, scaledViewport.height, scale)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }, [page, onDimensions])

  // Load PDF document and render immediately once ready
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    pdfRef.current = null

    getPdfjs().then(async (pdfjs) => {
      try {
        const doc = await pdfjs.getDocument({ url, withCredentials: true }).promise
        if (cancelled) return
        pdfRef.current = doc
        onPageCount?.(doc.numPages)
        await renderPage()
      } catch (e) {
        if (!cancelled) {
          setError(String(e))
          setLoading(false)
        }
      }
    })

    return () => { cancelled = true }
  }, [url]) // eslint-disable-line react-hooks/exhaustive-deps

  // Re-render when page index changes (doc already loaded)
  useEffect(() => {
    if (pdfRef.current) renderPage()
  }, [page, renderPage])

  return (
    <div ref={containerRef} className="relative w-full">
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-900/70 z-10 rounded">
          <div className="flex flex-col items-center gap-2">
            <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-gray-400 text-sm">Rendering…</span>
          </div>
        </div>
      )}
      {error && (
        <div className="p-4 text-red-400 text-sm">{error}</div>
      )}
      <canvas ref={canvasRef} className="w-full rounded shadow-xl" />
      {overlay && (
        <div className="absolute inset-0 pointer-events-none" style={{ top: 0, left: 0 }}>
          {overlay}
        </div>
      )}
    </div>
  )
}
