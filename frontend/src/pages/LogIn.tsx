import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'

export default function LogIn() {
  const { login } = useAuth()
  const navigate = useNavigate()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await login(email, password)
      navigate('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not log in.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page">
      <div className="shell form-wrap">
        <div className="page-head" style={{ textAlign: 'center' }}>
          <h1 style={{ fontSize: 28 }}>Welcome back</h1>
          <p style={{ margin: '10px auto 0' }}>
            Log in to pick up your conversation with our merch assistant.
          </p>
        </div>

        <div className="form-card">
          {error && <div className="alert">{error}</div>}

          <form onSubmit={submit}>
            <div className="field">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@yale.edu"
                required
              />
            </div>

            <div className="field">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
              />
            </div>

            <button
              className="btn btn-dark btn-block"
              type="submit"
              disabled={busy || !email || !password}
            >
              {busy ? 'Logging in…' : 'Log in'}
            </button>
          </form>

          <p className="note">
            New to Campus Customs? <Link to="/create-account">Create an account</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
