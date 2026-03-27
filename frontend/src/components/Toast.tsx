import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import type { Toast, ToastType } from '../types'

interface ToastContextValue {
  addToast: (message: string, type?: ToastType) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const COLORS: Record<ToastType, string> = {
  success: 'bg-green-50 border-green-200 text-green-800',
  warning: 'bg-yellow-50 border-yellow-200 text-yellow-800',
  error: 'bg-red-50 border-red-200 text-red-800',
  info: 'bg-blue-50 border-blue-200 text-blue-800',
}

const ICONS: Record<ToastType, React.ReactNode> = {
  success: (
    <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
  ),
  warning: (
    <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" /><line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" /></svg>
  ),
  error: (
    <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" /></svg>
  ),
  info: (
    <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><line x1="12" y1="16" x2="12" y2="12" /><line x1="12" y1="8" x2="12.01" y2="8" /></svg>
  ),
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const timers = useRef<Set<ReturnType<typeof setTimeout>>>(new Set())

  useEffect(() => {
    return () => { timers.current.forEach(clearTimeout) }
  }, [])

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.map((t) => t.id === id ? { ...t, leaving: true } : t))
    const t = setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
      timers.current.delete(t)
    }, 300)
    timers.current.add(t)
  }, [])

  const addToast = useCallback((message: string, type: ToastType = 'info') => {
    const id = crypto.randomUUID()
    setToasts((prev) => [...prev, { id, type, message }])
    const t = setTimeout(() => {
      dismiss(id)
      timers.current.delete(t)
    }, 5000)
    timers.current.add(t)
  }, [dismiss])

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full">
        {toasts.map((t) => (
          <ToastItem
            key={t.id}
            toast={t}
            onClose={() => dismiss(t.id)}
          />
        ))}
      </div>
    </ToastContext.Provider>
  )
}

function ToastItem({ toast, onClose }: { toast: Toast; onClose: () => void }) {
  return (
    <div
      className={`flex items-start gap-3 border rounded-lg px-4 py-3 shadow-lg text-sm transition-all duration-300 ${
        toast.leaving ? 'animate-out slide-out-to-right fade-out opacity-0' : 'animate-in slide-in-from-right'
      } ${COLORS[toast.type]}`}
    >
      <span className="mt-0.5">{ICONS[toast.type]}</span>
      <p className="flex-1 leading-5">{toast.message}</p>
      <button onClick={onClose} aria-label="Dismiss notification" className="opacity-50 hover:opacity-100 cursor-pointer transition-opacity ml-1">
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
      </button>
    </div>
  )
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
