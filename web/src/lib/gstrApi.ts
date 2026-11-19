import { getAccessToken } from './supabase'

export const GSTR_API_URL = (import.meta.env.VITE_GSTR_API_URL || 'http://localhost:8789').replace(/\/$/, '')

export type Gst9cCase = {
  id: string
  client_id: string
  registration_id: string
  gstin: string
  financial_year: string
  assigned_to: string | null
  status: string
  notes: string | null
  created_at: string
  updated_at: string
}

export type GstImportJob = {
  id: string
  case_id: string | null
  job_type: string
  status: string
  progress: number
  error_message: string | null
  result: Record<string, unknown>
  created_at: string
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await getAccessToken()
  const headers = new Headers(init.headers)
  headers.set('Authorization', `Bearer ${token}`)
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const res = await fetch(`${GSTR_API_URL}${path.startsWith('/') ? path : `/${path}`}`, {
    ...init,
    headers,
  })
  const text = await res.text()
  let body: unknown = null
  try {
    body = text ? JSON.parse(text) : null
  } catch {
    body = { raw: text }
  }
  if (!res.ok) {
    const detail =
      body && typeof body === 'object' && body !== null && 'detail' in body
        ? String((body as { detail: unknown }).detail)
        : `GSTR API error (${res.status})`
    throw new Error(detail)
  }
  return body as T
}

export const gstrApi = {
  health() {
    return fetch(`${GSTR_API_URL}/health`).then((r) => r.json())
  },

  dashboard() {
    return request<{
      total_cases: number
      pending_documents: number
      reconciling: number
      awaiting_review: number
      completed: number
    }>('/api/v1/gst/dashboard')
  },

  listCases(clientId?: string) {
    const q = clientId ? `?client_id=${encodeURIComponent(clientId)}` : ''
    return request<{ cases: Gst9cCase[] }>(`/api/v1/gst/cases${q}`)
  },

  getCase(caseId: string) {
    return request<{
      case: Gst9cCase
      documents: Array<Record<string, unknown>>
      jobs: GstImportJob[]
      reconciliation_runs: Array<Record<string, unknown>>
      drafts: Array<Record<string, unknown>>
      exports: Array<Record<string, unknown>>
    }>(`/api/v1/gst/cases/${caseId}`)
  },

  createCase(input: {
    client_id: string
    registration_id: string
    financial_year: string
    assigned_to?: string | null
    notes?: string | null
    validate_gstin?: boolean
  }) {
    return request<{ case: Gst9cCase }>('/api/v1/gst/cases', {
      method: 'POST',
      body: JSON.stringify(input),
    })
  },

  fetchReturns(caseId: string, body?: { return_types?: string[]; tax_periods?: string[] }) {
    return request<{ job_id: string; status: string }>(`/api/v1/gst/cases/${caseId}/fetch-returns`, {
      method: 'POST',
      body: JSON.stringify(body ?? {}),
    })
  },

  async uploadDocument(caseId: string, file: File, docType: string) {
    const token = await getAccessToken()
    const fd = new FormData()
    fd.append('file', file)
    fd.append('doc_type', docType)
    const res = await fetch(`${GSTR_API_URL}/api/v1/gst/cases/${caseId}/documents`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: fd,
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data?.detail || `Upload failed (${res.status})`)
    return data as { job_id: string; status: string }
  },

  reconcile(caseId: string, comparison_types?: string[]) {
    return request<{ job_id: string; status: string }>(`/api/v1/gst/cases/${caseId}/reconcile`, {
      method: 'POST',
      body: JSON.stringify({ comparison_types }),
    })
  },

  getReconciliation(
    caseId: string,
    filters?: { match_status?: string; comparison_type?: string; invoice_number?: string },
  ) {
    const params = new URLSearchParams()
    if (filters?.match_status) params.set('match_status', filters.match_status)
    if (filters?.comparison_type) params.set('comparison_type', filters.comparison_type)
    if (filters?.invoice_number) params.set('invoice_number', filters.invoice_number)
    const q = params.toString() ? `?${params}` : ''
    return request<{ runs: Array<Record<string, unknown>>; items: Array<Record<string, unknown>> }>(
      `/api/v1/gst/cases/${caseId}/reconciliation${q}`,
    )
  },

  generate(caseId: string) {
    return request<{ job_id: string; status: string }>(`/api/v1/gst/cases/${caseId}/generate`, {
      method: 'POST',
      body: JSON.stringify({}),
    })
  },

  preview(caseId: string) {
    return request<{
      draft: Record<string, unknown> | null
      values: Array<Record<string, unknown>>
      adjustments: Array<Record<string, unknown>>
    }>(`/api/v1/gst/cases/${caseId}/preview`)
  },

  addAdjustment(
    caseId: string,
    body: { table_code?: string; field_key?: string; amount: number; explanation: string },
  ) {
    return request<{ adjustment: Record<string, unknown> }>(`/api/v1/gst/cases/${caseId}/adjustments`, {
      method: 'POST',
      body: JSON.stringify(body),
    })
  },

  approve(caseId: string) {
    return request<{ case: Gst9cCase }>(`/api/v1/gst/cases/${caseId}/approve`, {
      method: 'POST',
      body: '{}',
    })
  },

  export(caseId: string, export_type: 'reconciliation_excel' | 'gstr9c_excel' | 'gstr9c_pdf') {
    return request<{ job_id: string; status: string }>(`/api/v1/gst/cases/${caseId}/exports`, {
      method: 'POST',
      body: JSON.stringify({ export_type }),
    })
  },

  getJob(jobId: string) {
    return request<{ job: GstImportJob }>(`/api/v1/gst/jobs/${jobId}`)
  },

  async pollJob(jobId: string, { intervalMs = 1500, timeoutMs = 180_000 } = {}) {
    const start = Date.now()
    while (Date.now() - start < timeoutMs) {
      const { job } = await this.getJob(jobId)
      if (job.status === 'succeeded' || job.status === 'failed' || job.status === 'cancelled') {
        if (job.status === 'failed') throw new Error(job.error_message || 'Job failed')
        return job
      }
      await new Promise((r) => setTimeout(r, intervalMs))
    }
    throw new Error('Job timed out')
  },

  async runJob(start: () => Promise<{ job_id: string }>) {
    const { job_id } = await start()
    return this.pollJob(job_id)
  },

  async downloadExport(exportId: string) {
    const token = await getAccessToken()
    const res = await fetch(`${GSTR_API_URL}/api/v1/gst/exports/${exportId}/download`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!res.ok) throw new Error(`Download failed (${res.status})`)
    return res.blob()
  },
}

export function currentFy(): string {
  const now = new Date()
  const year = now.getFullYear()
  const month = now.getMonth() + 1
  return month >= 4 ? `${year}-${String(year + 1).slice(2)}` : `${year - 1}-${String(year).slice(2)}`
}
