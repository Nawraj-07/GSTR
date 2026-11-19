import { createClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined
const anon = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined

if (!url || !anon) {
  console.warn('Missing VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY')
}

export const supabase = createClient(url || 'http://localhost', anon || 'missing', {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
})

export type Profile = {
  id: string
  email: string | null
  full_name: string | null
  company_name: string | null
  role: 'client' | 'employee' | 'admin' | string
  is_active: boolean | null
  gstin?: string | null
}

export type GstRegistration = {
  id: string
  client_id: string
  gstin: string
  legal_name: string | null
  trade_name: string | null
}

export async function getAccessToken(): Promise<string> {
  const { data, error } = await supabase.auth.getSession()
  if (error) throw error
  const token = data.session?.access_token
  if (!token) throw new Error('Not signed in')
  return token
}

export async function fetchAccessibleClients(): Promise<Profile[]> {
  const { data, error } = await supabase.rpc('get_my_accessible_clients')
  if (error) {
    // Fallback: staff may still read profiles they can see via RLS
    const fallback = await supabase
      .from('profiles')
      .select('id,email,full_name,company_name,role,is_active,gstin')
      .eq('role', 'client')
      .order('company_name')
    if (fallback.error) throw error
    return (fallback.data ?? []) as Profile[]
  }
  return (data ?? []) as Profile[]
}

export async function fetchRegistrations(clientId?: string): Promise<GstRegistration[]> {
  let q = supabase
    .from('gst_registrations')
    .select('id,client_id,gstin,legal_name,trade_name')
    .order('gstin')
  if (clientId) q = q.eq('client_id', clientId)
  const { data, error } = await q
  if (error) throw error
  return (data ?? []) as GstRegistration[]
}

export async function fetchEmployees(): Promise<Profile[]> {
  const { data, error } = await supabase
    .from('profiles')
    .select('id,email,full_name,company_name,role,is_active')
    .in('role', ['employee', 'admin'])
    .eq('is_active', true)
    .order('full_name')
  if (error) throw error
  return (data ?? []) as Profile[]
}

export async function fetchMyProfile(userId: string): Promise<Profile | null> {
  const { data, error } = await supabase
    .from('profiles')
    .select('id,email,full_name,company_name,role,is_active')
    .eq('id', userId)
    .maybeSingle()
  if (error) throw error
  return data as Profile | null
}
