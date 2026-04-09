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
  zoom?: number  // multiplier on top of fit-to-width scale; default 1
  onPageCount?: (n: number) => void
  onDimensions?: (w: number, h: number, scale: number) => void
  overlay?: React.ReactNode
  scrollContainerRef?: React.RefObject<HTMLDivElement | null>
  /** If provided, render this image URL instead of using PDF.js (used for .ai rasterized preview) */
  imageUrl?: string
  /** Known page width/height in PDF points (needed for image overlay scaling) */
  pagePoints?: { width: number; height: number }
}

export function PdfViewer({ url, page, zoom = 1, onPageCount, onDimensions, overlay, scrollContainerRef, imageUrl, pagePoints }: PdfViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const pdfRef = useRef<import('pdfjs-dist').PDFDocumentProxy | null>(null)

  const recenter = useCallback(() => {
    if (scrollContainerRef?.current) {
      const el = scrollContainerRef.current
      el.scrollLeft = (el.scrollWidth - el.clientWidth) / 2
      el.scrollTop = (el.scrollHeight - el.clientHeight) / 2
    }
  }, [scrollContainerRef])

  const renderPage = useCallback(async () => {
    const doc = pdfRef.current
    if (!doc || !canvasRef.current) return
    setLoading(true)
    try {
      const pdfPage = await doc.getPage(page + 1) // PDF.js is 1-based
      const container = containerRef.current
      const containerWidth = container?.clientWidth ?? 800
      const viewport = pdfPage.getViewport({ scale: 1 })
      const baseScale = containerWidth / viewport.width
      const scale = baseScale * zoom
      const scaledViewport = pdfPage.getViewport({ scale })

      const canvas = canvasRef.current
      canvas.width = scaledViewport.width
      canvas.height = scaledViewport.height

      const ctx = canvas.getContext('2d')!
      await pdfPage.render({ canvasContext: ctx, viewport: scaledViewport }).promise
      onDimensions?.(scaledViewport.width, scaledViewport.height, scale)
      recenter()
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }, [page, zoom, onDimensions, recenter])

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

  // Image-based preview (for .ai files)
  if (imageUrl) {
    return (
      <ImageViewer
        imageUrl={imageUrl}
        zoom={zoom}
        pagePoints={pagePoints}
        onDimensions={onDimensions}
        scrollContainerRef={scrollContainerRef}
        overlay={overlay}
      />
    )
  }

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
      <div className="relative inline-block">
        <canvas ref={canvasRef} className="block rounded shadow-xl" />
        {overlay && (
          <div className="absolute inset-0 pointer-events-none">
            {overlay}
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// ImageViewer — renders rasterized PNG with the same overlay support
// ---------------------------------------------------------------------------

interface ImageViewerProps {
  imageUrl: string
  zoom: number
  pagePoints?: { width: number; height: number }
  onDimensions?: (w: number, h: number, scale: number) => void
  scrollContainerRef?: React.RefObject<HTMLDivElement | null>
  overlay?: React.ReactNode
}

function ImageViewer({ imageUrl, zoom, pagePoints, onDimensions, scrollContainerRef, overlay }: ImageViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const imgRef = useRef<HTMLImageElement>(null)
  const [imgSize, setImgSize] = useState<{ w: number; h: number } | null>(null)

  const updateDims = useCallback((w: number, h: number) => {
    if (pagePoints) {
      const scale = w / pagePoints.width
      onDimensions?.(w * zoom, h * zoom, scale * zoom)
    }
  }, [pagePoints, zoom, onDimensions])

  const handleLoad = useCallback(() => {
    const img = imgRef.current
    if (!img) return
    const w = img.naturalWidth
    const h = img.naturalHeight
    setImgSize({ w, h })
    updateDims(w, h)

    // Re-center after image loads
    if (scrollContainerRef?.current) {
      const el = scrollContainerRef.current
      requestAnimationFrame(() => {
        el.scrollLeft = (el.scrollWidth - el.clientWidth) / 2
        el.scrollTop = (el.scrollHeight - el.clientHeight) / 2
      })
    }
  }, [updateDims, scrollContainerRef])

  // Update dimensions + re-center on zoom changes
  useEffect(() => {
    if (!imgSize) return
    updateDims(imgSize.w, imgSize.h)
    if (scrollContainerRef?.current) {
      const el = scrollContainerRef.current
      requestAnimationFrame(() => {
        el.scrollLeft = (el.scrollWidth - el.clientWidth) / 2
        el.scrollTop = (el.scrollHeight - el.clientHeight) / 2
      })
    }
  }, [zoom, imgSize, updateDims, scrollContainerRef])

  // Rendered size = natural pixels * zoom
  const renderW = imgSize ? imgSize.w * zoom : undefined
  const renderH = imgSize ? imgSize.h * zoom : undefined

  return (
    <div ref={containerRef} className="relative w-full">
      <div className="relative inline-block" style={renderW ? { width: renderW, height: renderH } : undefined}>
        <img
          ref={imgRef}
          src={imageUrl}
          onLoad={handleLoad}
          className="block rounded shadow-xl"
          style={renderW ? { width: renderW, height: renderH } : undefined}
          crossOrigin="use-credentials"
        />
        {overlay && (
          <div className="absolute inset-0 pointer-events-none">
            {overlay}
          </div>
        )}
      </div>
    </div>
  )
}
