import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useToast } from '@/components/Toast'
import { gstrApi } from '@/lib/gstrApi'

export default function ReportsPage() {
  const { caseId = '' } = useParams()
  const { push } = useToast()
  const [exports, setExports] = useState<Array<Record<string, unknown>>>([])
  const [busy, setBusy] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  async function refresh() {
    setLoading(true)
    try {
      const data = await gstrApi.getCase(caseId)
      setExports(data.exports)
    } catch (e) {
      push(e instanceof Error ? e.message : 'Failed to load exports', 'err')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [caseId])

  async function runExport(type: 'reconciliation_excel' | 'gstr9c_excel' | 'gstr9c_pdf', label: string) {
    setBusy(label)
    try {
      await gstrApi.runJob(() => gstrApi.export(caseId, type))
      await refresh()
      push(`${label} ready`)
    } catch (e) {
      push(e instanceof Error ? e.message : 'Export failed', 'err')
    } finally {
      setBusy(null)
    }
  }

  async function onDownload(exportId: string, fileName?: string) {
    try {
      const blob = await gstrApi.downloadExport(exportId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = fileName || 'export.bin'
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      push(e instanceof Error ? e.message : 'Download failed', 'err')
    }
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Reports</h1>
        <p className="text-sm text-ink-muted mt-1">
          <Link className="text-accent font-semibold" to={`/cases/${caseId}`}>
            Back to workspace
          </Link>
          {' · '}
          No automatic GST filing
        </p>
      </div>

      <div className="card mb-4 flex flex-wrap gap-2">
        <button
          type="button"
          className="btn btn-outline"
          disabled={!!busy}
          onClick={() => void runExport('reconciliation_excel', 'Reconciliation Excel')}
        >
          {busy === 'Reconciliation Excel' ? 'Working…' : 'Reconciliation Excel'}
        </button>
        <button
          type="button"
          className="btn btn-outline"
          disabled={!!busy}
          onClick={() => void runExport('gstr9c_excel', 'GSTR-9C Excel')}
        >
          {busy === 'GSTR-9C Excel' ? 'Working…' : 'GSTR-9C Excel'}
        </button>
        <button
          type="button"
          className="btn btn-primary"
          disabled={!!busy}
          onClick={() => void runExport('gstr9c_pdf', 'GSTR-9C PDF')}
        >
          {busy === 'GSTR-9C PDF' ? 'Working…' : 'GSTR-9C PDF'}
        </button>
      </div>

      <div className="card">
        <h2 className="font-bold text-sm mb-3">Generated files</h2>
        {loading ? (
          <p className="text-sm text-ink-muted">Loading…</p>
        ) : (
          <ul className="space-y-2">
            {exports.map((ex) => (
              <li
                key={String(ex.id)}
                className="flex items-center justify-between gap-2 text-sm border border-border rounded-lg px-3 py-2"
              >
                <div>
                  <div className="font-semibold">{String(ex.file_name || ex.export_type)}</div>
                  <div className="text-xs text-ink-muted">
                    {String(ex.export_type)} · {String(ex.status)} ·{' '}
                    {ex.created_at ? new Date(String(ex.created_at)).toLocaleString() : ''}
                  </div>
                </div>
                {ex.status === 'ready' && (
                  <button
                    type="button"
                    className="btn btn-outline text-xs"
                    onClick={() => void onDownload(String(ex.id), String(ex.file_name || ''))}
                  >
                    Download
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
        {!loading && !exports.length && <p className="text-xs text-ink-muted text-center py-8">No exports yet.</p>}
      </div>
    </div>
  )
}
