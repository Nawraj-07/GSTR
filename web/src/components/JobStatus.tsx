import type { GstImportJob } from '@/lib/gstrApi'

export function JobStatusList({ jobs }: { jobs: GstImportJob[] }) {
  if (!jobs.length) {
    return <p className="text-sm text-ink-muted">No jobs yet.</p>
  }
  return (
    <div className="space-y-2 max-h-72 overflow-auto">
      {jobs.map((j) => (
        <div key={j.id} className="rounded-lg border border-border px-3 py-2 text-xs">
          <div className="flex justify-between gap-2">
            <span className="font-semibold">{j.job_type}</span>
            <span className="badge">{j.status}</span>
          </div>
          <div className="text-ink-muted mt-1">
            {Math.round(Number(j.progress) || 0)}% · {new Date(j.created_at).toLocaleString()}
          </div>
          {j.error_message && <p className="text-danger mt-1">{j.error_message}</p>}
        </div>
      ))}
    </div>
  )
}
