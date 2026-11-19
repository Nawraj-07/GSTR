import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '@/store/auth'
import { GSTR_API_URL } from '@/lib/gstrApi'

export default function LoginPage() {
  const { session, loading, signIn, error } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)

  if (!loading && session) return <Navigate to="/" replace />

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setLocalError(null)
    try {
      await signIn(email.trim(), password)
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : 'Sign-in failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen grid place-items-center px-4">
      <div className="card w-full max-w-md">
        <div className="text-xs font-bold uppercase tracking-[0.14em] text-accent">GSTR-9C</div>
        <h1 className="text-2xl font-bold mt-2">Workbench login</h1>
        <p className="text-sm text-ink-muted mt-1">
          Use your FinAxis employee/admin account. API: <code className="text-xs">{GSTR_API_URL}</code>
        </p>

        <form onSubmit={onSubmit} className="mt-6 space-y-3">
          <label className="block text-xs font-semibold text-ink-muted">
            Email
            <input
              className="input mt-1"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <label className="block text-xs font-semibold text-ink-muted">
            Password
            <input
              className="input mt-1"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          {(localError || error) && (
            <p className="text-sm text-danger">{localError || error}</p>
          )}
          <button type="submit" className="btn btn-primary w-full" disabled={busy || loading}>
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
}
