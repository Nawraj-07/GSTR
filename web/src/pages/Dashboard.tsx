import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { gstrApi } from '@/lib/gstrApi'

export default function DashboardPage() {
  const [stats, setStats] = useState<{
    total_cases: number
    pending_documents: number
    reconciling: number
    awaiting_review: number
    completed: number
  } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        const data = await gstrApi.dashboard()
        if (alive) setStats(data)
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : 'Failed to load dashboard')
      } finally {
        if (alive) setLoading(false)
      }
    })()
    return () => {
      alive = false
    }
  }, [])

  return (
    <div>
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-sm text-ink-muted mt-1">GSTR-9C preparation overview</p>
        </div>
        <Link to="/cases" className="btn btn-primary">
          Open cases
        </Link>
      </div>

      {loading && <p className="text-sm text-ink-muted">Loading…</p>}
      {error && (
        <div className="card text-sm text-danger mb-4">
          {error}
          <p className="text-ink-muted mt-2">
            Ensure the GSTR API is running on port 8789 and the 9C migration is applied.
          </p>
        </div>
      )}

      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-6">
          {[
            ['Total cases', stats.total_cases],
            ['Pending documents', stats.pending_documents],
            ['Reconciling', stats.reconciling],
            ['Awaiting review', stats.awaiting_review],
            ['Completed', stats.completed],
          ].map(([label, value]) => (
            <div key={String(label)} className="card">
              <div className="text-[11px] font-bold uppercase tracking-wide text-ink-muted">{label}</div>
              <div className="text-2xl font-bold mt-1">{value}</div>
            </div>
          ))}
        </div>
      )}

      <div className="card text-sm text-ink-muted leading-relaxed">
        Workflow: create a case → fetch GST returns → upload books (Excel/CSV) → reconcile → generate
        draft → adjust/approve → export. GSTR-9 portal fetch is pending verification; upload GSTR-9
        manually if needed. No automatic filing.
      </div>
    </div>
  )
}
