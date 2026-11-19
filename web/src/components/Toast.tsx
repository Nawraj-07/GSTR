import { createContext, useCallback, useContext, useMemo, useState } from 'react'

type ToastItem = { id: number; message: string; tone: 'ok' | 'err' }

const ToastCtx = createContext<{
  push: (message: string, tone?: 'ok' | 'err') => void
} | null>(null)

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])
  const push = useCallback((message: string, tone: 'ok' | 'err' = 'ok') => {
    const id = Date.now() + Math.random()
    setItems((prev) => [...prev, { id, message, tone }])
    window.setTimeout(() => setItems((prev) => prev.filter((t) => t.id !== id)), 4000)
  }, [])
  const value = useMemo(() => ({ push }), [push])
  return (
    <ToastCtx.Provider value={value}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 space-y-2 max-w-sm">
        {items.map((t) => (
          <div
            key={t.id}
            className={`rounded-lg px-3 py-2 text-sm shadow-lg border ${
              t.tone === 'err'
                ? 'bg-white border-danger text-danger'
                : 'bg-white border-accent text-ink'
            }`}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastCtx)
  if (!ctx) throw new Error('ToastProvider missing')
  return ctx
}
