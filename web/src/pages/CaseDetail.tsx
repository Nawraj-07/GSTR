import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { JobStatusList } from '@/components/JobStatus'
import { useToast } from '@/components/Toast'
import { gstrApi, type Gst9cCase, type GstImportJob } from '@/lib/gstrApi'

const DOC_TYPES = [
  { value: 'sales_register', label: 'Sales register' },
  { value: 'purchase_register', label: 'Purchase register' },
  { value: 'trial_balance', label: 'Trial balance' },
  { value: 'profit_and_loss', label: 'Profit & loss' },
  { value: 'balance_sheet', label: 'Balance sheet' },
  { value: 'gstr9', label: 'GSTR-9 (manual)' },
  { value: 'other', label: 'Other' },
]

export default function CaseDetailPage() {
  const { caseId = '' } = useParams()
  const { push } = useToast()
  const [caseRow, setCaseRow] = useState<Gst9cCase | null>(null)
  const [docs, setDocs] = useState<Array<Record<string, unknown>>>([])
  const [jobs, setJobs] = useState<GstImportJob[]>([])
  const [exports, setExports] = useState<Array<Record<string, unknown>>>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<string | null>(null)
  const [docType, setDocType] = useState('sales_register')

  const refresh = useCallback(async () => {
    if (!caseId) return
    const data = await gstrApi.getCase(caseId)
    setCaseRow(data.case)
    setDocs(data.documents)
    setJobs(data.jobs)
    setExports(data.exports)
  }, [caseId])

  useEffect(() => {
    let alive = true
    ;(async () => {
      setLoading(true)
      try {
        await refresh()
      } catch (e) {
        if (alive) push(e instanceof Error ? e.message : 'Failed to load case', 'err')
      } finally {
        if (alive) setLoading(false)
      }
    })()
    return () => {
      alive = false
    }
  }, [refresh, push])

  const checklist = useMemo(() => {
    const uploaded = new Set(docs.map((d) => String(d.doc_type)))
    return DOC_TYPES.map((t) => ({ ...t, done: uploaded.has(t.value) }))
  }, [docs])

  async function run(label: string, fn: () => Promise<unknown>) {
    setBusy(label)
    try {
      await fn()
      await refresh()
      push(`${label} completed`)
    } catch (e) {
      push(e instanceof Error ? e.message : `${label} failed`, 'err')
    } finally {
      setBusy(null)
    }
  }

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file || !caseId) return
    await run('Upload', () => gstrApi.runJob(() => gstrApi.uploadDocument(caseId, file, docType)))
  }

  if (loading) return <p className="text-sm text-ink-muted">Loading case…</p>
  if (!caseRow) return <p className="text-sm text-danger">Case not found</p>

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-3 mb-6">
        <div>
          <div className="text-xs text-ink-muted font-semibold uppercase tracking-wide">Case workspace</div>
          <h1 className="text-2xl font-bold font-mono mt-1">{caseRow.gstin}</h1>
          <p className="text-sm text-ink-muted mt-1">
            FY {caseRow.financial_year} · <span className="badge">{caseRow.status}</span>
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link className="btn btn-outline" to={`/cases/${caseId}/reconciliation`}>
            Reconciliation
          </Link>
          <Link className="btn btn-outline" to={`/cases/${caseId}/review`}>
            Review
          </Link>
          <Link className="btn btn-outline" to={`/cases/${caseId}/reports`}>
            Reports
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
        <div className="card lg:col-span-2 space-y-3">
          <h2 className="font-bold text-sm">Workflow actions</h2>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="btn btn-primary"
              disabled={!!busy}
              onClick={() => run('Fetch returns', () => gstrApi.runJob(() => gstrApi.fetchReturns(caseId)))}
            >
              {busy === 'Fetch returns' ? 'Fetching…' : '1. Fetch GST returns'}
            </button>
            <button
              type="button"
              className="btn btn-outline"
              disabled={!!busy}
              onClick={() => run('Reconcile', () => gstrApi.runJob(() => gstrApi.reconcile(caseId)))}
            >
              {busy === 'Reconcile' ? 'Running…' : '3. Reconcile'}
            </button>
            <button
              type="button"
              className="btn btn-outline"
              disabled={!!busy}
              onClick={() => run('Generate', () => gstrApi.runJob(() => gstrApi.generate(caseId)))}
            >
              {busy === 'Generate' ? 'Generating…' : '4. Generate draft'}
            </button>
            <button
              type="button"
              className="btn btn-outline"
              disabled={!!busy}
              onClick={() => run('Approve', () => gstrApi.approve(caseId))}
            >
              Approve
            </button>
          </div>
          <p className="text-xs text-ink-muted">
            Step 2: upload books below. Unavailable portal returns can be replaced with document upload.
          </p>
        </div>
        <div className="card text-xs space-y-2">
          <h2 className="font-bold text-sm">Details</h2>
          <div className="flex justify-between gap-2">
            <span className="text-ink-muted">Client</span>
            <span className="font-mono truncate">{caseRow.client_id.slice(0, 8)}…</span>
          </div>
          <div className="flex justify-between gap-2">
            <span className="text-ink-muted">Notes</span>
            <span className="text-right">{caseRow.notes || '—'}</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <div className="card space-y-3">
          <h2 className="font-bold text-sm">Document checklist</h2>
          <ul className="text-sm space-y-1">
            {checklist.map((d) => (
              <li key={d.value} className="flex justify-between gap-2">
                <span>{d.label}</span>
                <span className={d.done ? 'text-accent text-xs font-bold' : 'text-ink-muted text-xs'}>
                  {d.done ? 'Uploaded' : 'Pending'}
                </span>
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap items-end gap-2 pt-2 border-t border-border">
            <label className="text-xs font-semibold text-ink-muted flex-1 min-w-40">
              Type
              <select className="input mt-1" value={docType} onChange={(e) => setDocType(e.target.value)}>
                {DOC_TYPES.map((d) => (
                  <option key={d.value} value={d.value}>
                    {d.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="btn btn-primary cursor-pointer">
              {busy === 'Upload' ? 'Uploading…' : 'Upload Excel/CSV'}
              <input type="file" accept=".xlsx,.xls,.csv" className="hidden" disabled={!!busy} onChange={onFile} />
            </label>
          </div>
        </div>
        <div className="card space-y-3">
          <h2 className="font-bold text-sm">Recent jobs</h2>
          <JobStatusList jobs={jobs} />
        </div>
      </div>

      <div className="card">
        <h2 className="font-bold text-sm mb-2">Exports on this case</h2>
        <ul className="text-sm space-y-1">
          {exports.map((ex) => (
            <li key={String(ex.id)} className="flex justify-between gap-2">
              <span>
                {String(ex.file_name || ex.export_type)} · {String(ex.status)}
              </span>
              {ex.status === 'ready' && (
                <button
                  type="button"
                  className="btn btn-ghost text-xs"
                  onClick={async () => {
                    try {
                      const blob = await gstrApi.downloadExport(String(ex.id))
                      const url = URL.createObjectURL(blob)
                      const a = document.createElement('a')
                      a.href = url
                      a.download = String(ex.file_name || 'export.bin')
                      a.click()
                      URL.revokeObjectURL(url)
                    } catch (e) {
                      push(e instanceof Error ? e.message : 'Download failed', 'err')
                    }
                  }}
                >
                  Download
                </button>
              )}
            </li>
          ))}
        </ul>
        {!exports.length && <p className="text-xs text-ink-muted">No exports yet — use Reports.</p>}
      </div>
    </div>
  )
}
