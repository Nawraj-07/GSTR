import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { currentFy, gstrApi, type Gst9cCase } from '@/lib/gstrApi'
import {
  fetchAccessibleClients,
  fetchEmployees,
  fetchRegistrations,
  type GstRegistration,
  type Profile,
} from '@/lib/supabase'
import { useAuth } from '@/store/auth'
import { useToast } from '@/components/Toast'

export default function CasesPage() {
  const navigate = useNavigate()
  const { profile } = useAuth()
  const { push } = useToast()
  const [cases, setCases] = useState<Gst9cCase[]>([])
  const [clients, setClients] = useState<Profile[]>([])
  const [employees, setEmployees] = useState<Profile[]>([])
  const [regs, setRegs] = useState<GstRegistration[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [busy, setBusy] = useState(false)

  const [clientId, setClientId] = useState('')
  const [registrationId, setRegistrationId] = useState('')
  const [fy, setFy] = useState(currentFy())
  const [assignedTo, setAssignedTo] = useState('')
  const [notes, setNotes] = useState('')

  const clientRegs = useMemo(
    () => regs.filter((r) => r.client_id === clientId),
    [regs, clientId],
  )

  async function refresh() {
    setLoading(true)
    try {
      const [{ cases: rows }, c, e, r] = await Promise.all([
        gstrApi.listCases(),
        fetchAccessibleClients(),
        fetchEmployees(),
        fetchRegistrations(),
      ])
      setCases(rows)
      setClients(c)
      setEmployees(e)
      setRegs(r)
    } catch (err) {
      push(err instanceof Error ? err.message : 'Failed to load cases', 'err')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  async function onCreate(e: React.FormEvent) {
    e.preventDefault()
    if (!clientId || !registrationId || !fy.trim()) {
      push('Client, GSTIN registration, and FY are required', 'err')
      return
    }
    setBusy(true)
    try {
      const { case: created } = await gstrApi.createCase({
        client_id: clientId,
        registration_id: registrationId,
        financial_year: fy.trim(),
        assigned_to: assignedTo || null,
        notes: notes || null,
        validate_gstin: true,
      })
      push('Case created')
      navigate(`/cases/${created.id}`)
    } catch (err) {
      push(err instanceof Error ? err.message : 'Create failed', 'err')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold">Cases</h1>
          <p className="text-sm text-ink-muted mt-1">Client + GSTIN + financial year</p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setShowForm((v) => !v)}>
          {showForm ? 'Close' : 'New case'}
        </button>
      </div>

      {showForm && (
        <form onSubmit={onCreate} className="card mb-6 grid grid-cols-1 md:grid-cols-2 gap-3">
          <label className="text-xs font-semibold text-ink-muted">
            Client
            <select
              className="input mt-1"
              value={clientId}
              onChange={(e) => {
                setClientId(e.target.value)
                setRegistrationId('')
              }}
            >
              <option value="">Select…</option>
              {clients.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.company_name || c.full_name || c.email}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs font-semibold text-ink-muted">
            GSTIN registration
            <select
              className="input mt-1"
              value={registrationId}
              onChange={(e) => setRegistrationId(e.target.value)}
              disabled={!clientId}
            >
              <option value="">Select…</option>
              {clientRegs.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.gstin} {r.legal_name ? `— ${r.legal_name}` : ''}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs font-semibold text-ink-muted">
            Financial year
            <input className="input mt-1" value={fy} onChange={(e) => setFy(e.target.value)} />
          </label>
          <label className="text-xs font-semibold text-ink-muted">
            Assignee
            <select className="input mt-1" value={assignedTo} onChange={(e) => setAssignedTo(e.target.value)}>
              <option value="">— Unassigned —</option>
              {profile && <option value={profile.id}>Me ({profile.full_name})</option>}
              {employees
                .filter((e) => e.id !== profile?.id)
                .map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.full_name}
                  </option>
                ))}
            </select>
          </label>
          <label className="text-xs font-semibold text-ink-muted md:col-span-2">
            Notes
            <textarea className="input mt-1 min-h-20" value={notes} onChange={(e) => setNotes(e.target.value)} />
          </label>
          <div className="md:col-span-2 flex justify-end">
            <button type="submit" className="btn btn-primary" disabled={busy}>
              {busy ? 'Creating…' : 'Create case'}
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <p className="text-sm text-ink-muted">Loading…</p>
      ) : (
        <div className="card overflow-x-auto">
          <table className="table">
            <thead>
              <tr>
                <th>GSTIN</th>
                <th>FY</th>
                <th>Status</th>
                <th>Updated</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.id}>
                  <td className="font-mono text-xs">{c.gstin}</td>
                  <td>{c.financial_year}</td>
                  <td>
                    <span className="badge">{c.status}</span>
                  </td>
                  <td className="text-xs text-ink-muted">{new Date(c.updated_at).toLocaleString()}</td>
                  <td className="text-right">
                    <Link className="btn btn-outline text-xs" to={`/cases/${c.id}`}>
                      Open
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!cases.length && <p className="text-sm text-ink-muted py-6 text-center">No cases yet.</p>}
        </div>
      )}
    </div>
  )
}
