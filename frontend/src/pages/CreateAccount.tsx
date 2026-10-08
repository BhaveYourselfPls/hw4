import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'

const MIN_PASSWORD = 8

export default function CreateAccount() {
  const { signup } = useAuth()
  const navigate = useNavigate()

  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    email: '',
    password: '',
  })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [key]: e.target.value }))

  const ready =
    Object.values(form).every((value) => value.trim().length > 0) &&
    form.password.length >= MIN_PASSWORD

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await signup({
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        email: form.email.trim(),
        password: form.password,
      })
      navigate('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create your account.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page">
      <div className="shell form-wrap">
        <div className="page-head" style={{ textAlign: 'center' }}>
          <h1 style={{ fontSize: 28 }}>Create your account</h1>
          <p style={{ margin: '10px auto 0' }}>
            Save your sizes and keep your chat history with our merch assistant.
          </p>
        </div>

        <div className="form-card">
          {error && <div className="alert">{error}</div>}

          <form onSubmit={submit}>
            <div className="row-2">
              <div className="field">
                <label htmlFor="firstName">First name</label>
                <input
                  id="firstName"
                  value={form.first_name}
                  onChange={set('first_name')}
                  placeholder="Ada"
                  autoComplete="given-name"
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="lastName">Last name</label>
                <input
                  id="lastName"
                  value={form.last_name}
                  onChange={set('last_name')}
                  placeholder="Lovelace"
                  autoComplete="family-name"
                  required
                />
              </div>
            </div>

            <div className="field">
              <label htmlFor="newEmail">Email</label>
              <input
                id="newEmail"
                type="email"
                autoComplete="email"
                value={form.email}
                onChange={set('email')}
                placeholder="you@yale.edu"
                required
              />
            </div>

            <div className="field">
              <label htmlFor="newPassword">Password</label>
              <input
                id="newPassword"
                type="password"
                autoComplete="new-password"
                value={form.password}
                onChange={set('password')}
                placeholder={`At least ${MIN_PASSWORD} characters`}
                required
              />
              {form.password.length > 0 && form.password.length < MIN_PASSWORD && (
                <p className="hint-text">
                  {MIN_PASSWORD - form.password.length} more character
                  {MIN_PASSWORD - form.password.length === 1 ? '' : 's'} needed.
                </p>
              )}
            </div>

            <button className="btn btn-dark btn-block" type="submit" disabled={busy || !ready}>
              {busy ? 'Creating account…' : 'Create account'}
            </button>
          </form>

          <p className="note">
            Already have one? <Link to="/login">Log in</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
