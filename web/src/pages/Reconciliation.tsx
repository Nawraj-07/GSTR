import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useToast } from '@/components/Toast'
import { gstrApi } from '@/lib/gstrApi'

export default function ReconciliationPage() {
  const { caseId = '' } = useParams()
  const { push } = useToast()
  const [matchStatus, setMatchStatus] = useState('')
  const [comparisonType, setComparisonType] = useState('')
  const [invoice, setInvoice] = useState('')
  const [runs, setRuns] = useState<Array<Record<string, unknown>>>([])
  const [items, setItems] = useState<Array<Record<string, unknown>>>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const data = await gstrApi.getReconciliation(caseId, {
        match_status: matchStatus || undefined,
        comparison_type: comparisonType || undefined,
        invoice_number: invoice || undefined,
      })
      setRuns(data.runs)
      setItems(data.items)
    } catch (e) {
      push(e instanceof Error ? e.message : 'Failed to load reconciliation', 'err')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [caseId])

  async function onRun() {
    setBusy(true)
    try {
      await gstrApi.runJob(() => gstrApi.reconcile(caseId))
      push('Reconciliation completed')
      await load()
    } catch (e) {
      push(e instanceof Error ? e.message : 'Reconcile failed', 'err')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-bold">Reconciliation</h1>
          <p className="text-sm text-ink-muted mt-1">
            <Link className="text-accent font-semibold" to={`/cases/${caseId}`}>
              Back to workspace
            </Link>
          </p>
        </div>
        <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void onRun()}>
          {busy ? 'Running…' : 'Run reconciliation'}
        </button>
      </div>

      <div className="card mb-4 grid grid-cols-1 md:grid-cols-4 gap-3">
        <label className="text-xs font-semibold text-ink-muted">
          Comparison
          <select className="input mt-1" value={comparisonType} onChange={(e) => setComparisonType(e.target.value)}>
            <option value="">All</option>
            <option value="gstr1_vs_sales">GSTR-1 vs Sales</option>
            <option value="gstr3b_vs_gstr1">GSTR-3B vs GSTR-1</option>
            <option value="gstr2b_vs_purchases">GSTR-2B vs Purchases</option>
            <option value="gstr9_vs_financials">GSTR-9 vs Financials</option>
            <option value="books_vs_returns">Books vs Returns</option>
          </select>
        </label>
        <label className="text-xs font-semibold text-ink-muted">
          Match status
          <select className="input mt-1" value={matchStatus} onChange={(e) => setMatchStatus(e.target.value)}>
            <option value="">All</option>
            <option value="matched">Matched</option>
            <option value="partially_matched">Partially matched</option>
            <option value="mismatched">Mismatched</option>
            <option value="missing_in_gst">Missing in GST</option>
            <option value="missing_in_books">Missing in books</option>
          </select>
        </label>
        <label className="text-xs font-semibold text-ink-muted">
          Invoice #
          <input className="input mt-1" value={invoice} onChange={(e) => setInvoice(e.target.value)} />
        </label>
        <div className="flex items-end">
          <button type="button" className="btn btn-outline w-full" onClick={() => void load()}>
            Apply filters
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        {runs.slice(0, 4).map((r) => {
          const summary = (r.summary || {}) as Record<string, unknown>
          return (
            <div key={String(r.id)} className="card">
              <div className="text-xs text-ink-muted font-semibold">{String(r.comparison_type)}</div>
              <div className="text-sm mt-1">
                Matched {String(summary.matched ?? 0)} · Diff {String(summary.net_difference ?? 0)}
              </div>
            </div>
          )
        })}
      </div>

      <div className="card overflow-x-auto">
        {loading ? (
          <p className="text-sm text-ink-muted">Loading…</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Invoice</th>
                <th>Diff</th>
                <th>Explanation</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => {
                const meta = (it.meta || {}) as Record<string, unknown>
                return (
                  <tr key={String(it.id)}>
                    <td className="text-xs font-semibold whitespace-nowrap">{String(it.match_status)}</td>
                    <td className="font-mono text-xs">{String(meta.invoice_number || '—')}</td>
                    <td className="text-xs">{String(it.difference_amount ?? '—')}</td>
                    <td className="text-xs text-ink-muted">{String(it.explanation || '')}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
        {!loading && !items.length && (
          <p className="text-xs text-ink-muted py-6 text-center">No items yet. Run reconciliation after importing data.</p>
        )}
      </div>
    </div>
  )
}
