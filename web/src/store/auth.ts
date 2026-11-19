import { useEffect, useState } from 'react'
import type { Session } from '@supabase/supabase-js'
import { fetchMyProfile, supabase, type Profile } from '@/lib/supabase'

type AuthState = {
  session: Session | null
  profile: Profile | null
  loading: boolean
  error: string | null
}

export function useAuth() {
  const [state, setState] = useState<AuthState>({
    session: null,
    profile: null,
    loading: true,
    error: null,
  })

  useEffect(() => {
    let mounted = true

    async function load() {
      const { data } = await supabase.auth.getSession()
      const session = data.session
      if (!session) {
        if (mounted) setState({ session: null, profile: null, loading: false, error: null })
        return
      }
      try {
        const profile = await fetchMyProfile(session.user.id)
        if (!mounted) return
        if (!profile || !['employee', 'admin'].includes(profile.role) || profile.is_active === false) {
          await supabase.auth.signOut()
          setState({
            session: null,
            profile: null,
            loading: false,
            error: 'Only active FinAxis employees/admins can use this workbench.',
          })
          return
        }
        setState({ session, profile, loading: false, error: null })
      } catch (e) {
        if (mounted) {
          setState({
            session: null,
            profile: null,
            loading: false,
            error: e instanceof Error ? e.message : 'Auth failed',
          })
        }
      }
    }

    void load()
    const { data: sub } = supabase.auth.onAuthStateChange(() => {
      void load()
    })
    return () => {
      mounted = false
      sub.subscription.unsubscribe()
    }
  }, [])

  async function signIn(email: string, password: string) {
    setState((s) => ({ ...s, loading: true, error: null }))
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) {
      setState((s) => ({ ...s, loading: false, error: error.message }))
      throw error
    }
  }

  async function signOut() {
    await supabase.auth.signOut()
    setState({ session: null, profile: null, loading: false, error: null })
  }

  return { ...state, signIn, signOut }
}
