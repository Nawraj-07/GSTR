import { NavLink, Outlet, useParams } from 'react-router-dom'
import { useAuth } from '@/store/auth'

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `block rounded-lg px-3 py-2 text-sm font-semibold transition ${
    isActive ? 'bg-accent-soft text-accent' : 'text-ink-muted hover:bg-white hover:text-ink'
  }`

export function Layout() {
  const { profile, signOut } = useAuth()
  const { caseId } = useParams()

  return (
    <div className="min-h-screen grid lg:grid-cols-[240px_1fr]">
      <aside className="border-r border-border bg-white/80 backdrop-blur px-4 py-5">
        <div className="mb-6">
          <div className="text-xs font-bold uppercase tracking-[0.14em] text-accent">GSTR-9C</div>
          <h1 className="text-lg font-bold mt-1">Workbench</h1>
          <p className="text-xs text-ink-muted mt-1">FinAxis microservice console</p>
        </div>

        <nav className="space-y-1">
          <NavLink to="/" end className={linkClass}>
            Dashboard
          </NavLink>
          <NavLink to="/cases" className={linkClass}>
            Cases
          </NavLink>
        </nav>

        {caseId && (
          <div className="mt-6">
            <div className="text-[11px] font-bold uppercase tracking-wide text-ink-faint mb-2 px-3">
              This case
            </div>
            <nav className="space-y-1">
              <NavLink to={`/cases/${caseId}`} end className={linkClass}>
                Workspace
              </NavLink>
              <NavLink to={`/cases/${caseId}/reconciliation`} className={linkClass}>
                Reconciliation
              </NavLink>
              <NavLink to={`/cases/${caseId}/review`} className={linkClass}>
                Review
              </NavLink>
              <NavLink to={`/cases/${caseId}/reports`} className={linkClass}>
                Reports
              </NavLink>
            </nav>
          </div>
        )}

        <div className="mt-10 pt-4 border-t border-border">
          <div className="text-xs font-semibold">{profile?.full_name || 'User'}</div>
          <div className="text-xs text-ink-muted">{profile?.role}</div>
          <button type="button" className="btn btn-ghost mt-2 px-0" onClick={() => void signOut()}>
            Sign out
          </button>
        </div>
      </aside>

      <main className="px-5 py-6 lg:px-8">
        <Outlet />
      </main>
    </div>
  )
}
