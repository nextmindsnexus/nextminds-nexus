import { supabase } from '../lib/supabase'

const API_BASE = import.meta.env.VITE_API_BASE_URL?.trim().replace(/\/$/, '') || ''

/**
 * Authenticated fetch wrapper.
 * Injects Supabase JWT as Bearer token. Redirects to /login on 401.
 */
export async function apiFetch(path, options = {}) {
  const { data: { session } } = await supabase.auth.getSession()
  const token = session?.access_token

  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const url = path.startsWith('http') ? path : `${API_BASE}${path}`

  const res = await fetch(url, { ...options, headers })

  if (res.status === 401) {
    await supabase.auth.signOut()
    window.location.href = '/login'
    throw new Error('Session expired. Please log in again.')
  }

  return res
}
