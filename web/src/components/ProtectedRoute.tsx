import { Navigate } from 'react-router-dom'
import { useAuth } from '@/store/auth'

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { session, loading } = useAuth()
  if (loading) {
    return (
      <div className="min-h-screen grid place-items-center text-ink-muted text-sm">
        Checking session…
      </div>
    )
  }
  if (!session) return <Navigate to="/login" replace />
  return <>{children}</>
}
