import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { Toast, ToastType } from '../types'

interface ToastContextValue {
  addToast: (message: string, type?: ToastType) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const addToast = useCallback((message: string, type: ToastType = 'info') => {
    const id = Math.random().toString(36).slice(2)
    setToasts((prev) => [...prev, { id, type, message }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 5000)
  }, [])

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full">
        {toasts.map((t) => (
          <ToastItem
            key={t.id}
            toast={t}
            onClose={() => setToasts((prev) => prev.filter((x) => x.id !== t.id))}
          />
        ))}
      </div>
    </ToastContext.Provider>
  )
}

function ToastItem({ toast, onClose }: { toast: Toast; onClose: () => void }) {
  const colors: Record<ToastType, string> = {
    success: 'bg-green-800 border-green-600 text-green-100',
    warning: 'bg-yellow-800 border-yellow-600 text-yellow-100',
    error: 'bg-red-800 border-red-600 text-red-100',
    info: 'bg-blue-800 border-blue-600 text-blue-100',
  }
  const icons: Record<ToastType, string> = {
    success: '✓',
    warning: '⚠',
    error: '✗',
    info: 'ℹ',
  }

  return (
    <div
      className={`flex items-start gap-3 border rounded-lg px-4 py-3 shadow-lg text-sm animate-in slide-in-from-right ${colors[toast.type]}`}
    >
      <span className="font-bold text-base leading-5">{icons[toast.type]}</span>
      <p className="flex-1 leading-5">{toast.message}</p>
      <button onClick={onClose} className="opacity-70 hover:opacity-100 text-base leading-5">
        ×
      </button>
    </div>
  )
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
