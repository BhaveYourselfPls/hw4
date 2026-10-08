import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

export interface User {
  id: number
  first_name: string | null
  last_name: string | null
  name: string
  email: string
  created_at: string
}

interface AuthResponse {
  token: string
  user: User
}

const TOKEN_KEY = 'cc_token'

/** Surfaces the backend's `detail` message instead of a bare status code. */
async function postAuth(path: string, body: unknown): Promise<AuthResponse> {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = (data as { detail?: unknown }).detail
    throw new Error(typeof detail === 'string' ? detail : 'Something went wrong. Please try again.')
  }
  return data as AuthResponse
}

interface AuthContextValue {
  user: User | null
  loading: boolean
  signup: (input: {
    first_name: string
    last_name: string
    email: string
    password: string
  }) => Promise<void>
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  // Restore the session on load: the token lives in localStorage, but the user
  // is always re-fetched so a revoked or expired token fails closed.
  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY)
    if (!token) {
      setLoading(false)
      return
    }
    fetch('/api/auth/me', { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then(setUser)
      .catch(() => localStorage.removeItem(TOKEN_KEY))
      .finally(() => setLoading(false))
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      async signup(input) {
        const data = await postAuth('/api/auth/signup', input)
        localStorage.setItem(TOKEN_KEY, data.token)
        setUser(data.user)
      },
      async login(email, password) {
        const data = await postAuth('/api/auth/login', { email, password })
        localStorage.setItem(TOKEN_KEY, data.token)
        setUser(data.user)
      },
      logout() {
        localStorage.removeItem(TOKEN_KEY)
        setUser(null)
      },
    }),
    [user, loading],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>')
  return context
}

/** Token accessor for non-React callers (e.g. the chat client, later). */
export const getToken = () => localStorage.getItem(TOKEN_KEY)
