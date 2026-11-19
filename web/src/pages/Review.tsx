import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useToast } from '@/components/Toast'
import { gstrApi } from '@/lib/gstrApi'

export default function ReviewPage() {
  const { caseId = '' } = useParams()
  const { push } = useToast()
  const [draft, setDraft] = useState<Record<string, unknown> | null>(null)
  const [values, setValues] = useState<Array<Record<string, unknown>>>([])
  const [adjustments, setAdjustments] = useState<Array<Record<string, unknown>>>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [tableCode, setTableCode] = useState('pt_ii_5')
  const [fieldKey, setFieldKey] = useState('5k')
  const [amount, setAmount] = useState('0')
  const [explanation, setExplanation] = useState('')

  async function load() {
    setLoading(true)
    try {
      const data = await gstrApi.preview(caseId)
      setDraft(data.draft)
      setValues(data.values)
      setAdjustments(data.adjustments)
    } catch (e) {
      push(e instanceof Error ? e.message : 'Failed to load preview', 'err')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [caseId])

  const grouped = useMemo(() => {
    const map = new Map<string, Array<Record<string, unknown>>>()
    for (const v of values) {
      const key = String(v.table_code)
      if (!map.has(key)) map.set(key, [])
      map.get(key)!.push(v)
    }
    return [...map.entries()]
  }, [values])

  async function onGenerate() {
    setBusy(true)
    try {
      await gstrApi.runJob(() => gstrApi.generate(caseId))
      await load()
      push('Draft generated')
    } catch (e) {
      push(e instanceof Error ? e.message : 'Generate failed', 'err')
    } finally {
      setBusy(false)
    }
  }

  async function onAdjust(e: React.FormEvent) {
    e.preventDefault()
    if (!explanation.trim()) {
      push('Explanation required', 'err')
      return
    }
    setBusy(true)
    try {
      await gstrApi.addAdjustment(caseId, {
        table_code: tableCode,
        field_key: fieldKey,
        amount: Number(amount) || 0,
        explanation: explanation.trim(),
      })
      setExplanation('')
      await load()
      push('Adjustment saved — regenerate to apply')
    } catch (err) {
      push(err instanceof Error ? err.message : 'Failed', 'err')
    } finally {
      setBusy(false)
    }
  }

  async function onApprove() {
    setBusy(true)
    try {
      await gstrApi.approve(caseId)
      push('Case approved')
      await load()
    } catch (e) {
      push(e instanceof Error ? e.message : 'Approve failed', 'err')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-bold">CA Review</h1>
          <p className="text-sm text-ink-muted mt-1">
            <Link className="text-accent font-semibold" to={`/cases/${caseId}`}>
              Back to workspace
            </Link>
          </p>
        </div>
        <div className="flex gap-2">
          <button type="button" className="btn btn-outline" disabled={busy} onClick={() => void onGenerate()}>
            {busy ? 'Working…' : 'Generate / refresh'}
          </button>
          <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void onApprove()}>
            Approve
          </button>
        </div>
      </div>

      {loading && <p className="text-sm text-ink-muted">Loading…</p>}

      {!loading && !draft && (
        <div className="card text-sm text-ink-muted">
          No draft yet. Fetch/upload data, reconcile, then generate a GSTR-9C draft.
          <div className="mt-3">
            <button type="button" className="btn btn-primary" onClick={() => void onGenerate()} disabled={busy}>
              Generate draft
            </button>
          </div>
        </div>
      )}

      {draft && (
        <>
          <div className="card mb-4 text-sm space-y-2">
            <div>
              Version {String(draft.version)} · Status {String(draft.status)} · Schema{' '}
              {String(draft.fy_schema_key)}
            </div>
            {!!(draft.summary as { disclaimer?: string } | undefined)?.disclaimer && (
              <p className="text-xs text-ink-muted">
                {(draft.summary as { disclaimer: string }).disclaimer}
              </p>
            )}
            {!!(draft.summary as { warnings?: Array<{ message?: string }> } | undefined)?.warnings?.length && (
              <ul className="text-xs text-warn list-disc pl-4">
                {((draft.summary as { warnings: Array<{ message?: string }> }).warnings).map((w, i) => (
                  <li key={i}>{w.message || JSON.stringify(w)}</li>
                ))}
              </ul>
            )}
          </div>

          <form onSubmit={onAdjust} className="card mb-4 grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
            <label className="text-xs font-semibold text-ink-muted">
              Table
              <input className="input mt-1" value={tableCode} onChange={(e) => setTableCode(e.target.value)} />
            </label>
            <label className="text-xs font-semibold text-ink-muted">
              Field
              <input className="input mt-1" value={fieldKey} onChange={(e) => setFieldKey(e.target.value)} />
            </label>
            <label className="text-xs font-semibold text-ink-muted">
              Amount
              <input className="input mt-1" value={amount} onChange={(e) => setAmount(e.target.value)} />
            </label>
            <button type="submit" className="btn btn-outline" disabled={busy}>
              Add adjustment
            </button>
            <label className="text-xs font-semibold text-ink-muted md:col-span-4">
              Explanation
              <input className="input mt-1" value={explanation} onChange={(e) => setExplanation(e.target.value)} />
            </label>
          </form>

          {adjustments.length > 0 && (
            <div className="card mb-4">
              <h2 className="font-bold text-sm mb-2">Adjustments</h2>
              <ul className="text-xs space-y-1">
                {adjustments.map((a) => (
                  <li key={String(a.id)}>
                    {String(a.table_code)}.{String(a.field_key)}: {String(a.amount)} — {String(a.explanation)}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="space-y-4">
            {grouped.map(([table, rows]) => (
              <div key={table} className="card overflow-x-auto">
                <h2 className="font-bold text-sm mb-2">{table}</h2>
                <table className="table">
                  <thead>
                    <tr>
                      <th>Row</th>
                      <th>Amount</th>
                      <th>Text</th>
                      <th>Sources</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((v) => (
                      <tr key={String(v.id)}>
                        <td className="font-mono text-xs">{String(v.row_key)}</td>
                        <td>{v.value == null ? '—' : String(v.value)}</td>
                        <td className="text-xs">{v.value_text ? String(v.value_text) : '—'}</td>
                        <td className="text-xs text-ink-muted">{JSON.stringify(v.source_refs)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
