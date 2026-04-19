import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabase'

export default function RegisterPage() {
  const [form, setForm] = useState({
    firstName: '',
    lastName: '',
    dateOfBirth: '',
    email: '',
    password: '',
    confirmPassword: '',
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  function updateField(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')

    if (form.password !== form.confirmPassword) {
      setError('Passwords do not match.')
      return
    }

    if (form.password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }

    setLoading(true)

    try {
      // Step 1: Register via backend (creates Supabase user + profile)
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: form.email,
          password: form.password,
          first_name: form.firstName,
          last_name: form.lastName,
          date_of_birth: form.dateOfBirth || null,
        }),
      })

      const data = await res.json()

      if (!res.ok) {
        setError(data.detail || 'Registration failed.')
        return
      }

      // Step 2: Auto sign in
      const { error: signInError } = await supabase.auth.signInWithPassword({
        email: form.email,
        password: form.password,
      })

      if (signInError) {
        setError('Account created but sign-in failed. Please log in manually.')
        setTimeout(() => navigate('/login'), 2000)
        return
      }

      navigate('/')
    } catch (err) {
      setError('Registration failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-brand">
        <div className="auth-brand-overlay">
          <img src="/nexus-logo.png" alt="NextMinds" className="auth-brand-logo" />
          <h2 className="auth-brand-heading">Nexus</h2>
          <p className="auth-brand-tagline">
            Your AI-powered curriculum assistant for smarter teaching
          </p>
        </div>
      </div>

      <div className="auth-form-side">
        <div className="auth-card">
          <h1 className="auth-title">Create Account</h1>
          <p className="auth-subtitle">Join Nexus to explore curriculum resources</p>

          <form className="auth-form" onSubmit={handleSubmit}>
            {error && <p className="auth-error">{error}</p>}

            <div className="auth-row">
              <label className="auth-label">
                First Name
                <input
                  type="text"
                  className="auth-input"
                  value={form.firstName}
                  onChange={(e) => updateField('firstName', e.target.value)}
                  required
                  placeholder="Jane"
                />
              </label>

              <label className="auth-label">
                Last Name
                <input
                  type="text"
                  className="auth-input"
                  value={form.lastName}
                  onChange={(e) => updateField('lastName', e.target.value)}
                  required
                  placeholder="Doe"
                />
              </label>
            </div>

            <label className="auth-label">
              Date of Birth
              <input
                type="date"
                className="auth-input"
                value={form.dateOfBirth}
                onChange={(e) => updateField('dateOfBirth', e.target.value)}
              />
            </label>

            <label className="auth-label">
              Email
              <input
                type="email"
                className="auth-input"
                value={form.email}
                onChange={(e) => updateField('email', e.target.value)}
                required
                autoComplete="email"
                placeholder="you@school.edu"
              />
            </label>

            <label className="auth-label">
              Password
              <input
                type="password"
                className="auth-input"
                value={form.password}
                onChange={(e) => updateField('password', e.target.value)}
                required
                minLength={8}
                placeholder="Min 8 characters"
              />
            </label>

            <label className="auth-label">
              Confirm Password
              <input
                type="password"
                className="auth-input"
                value={form.confirmPassword}
                onChange={(e) => updateField('confirmPassword', e.target.value)}
                required
                minLength={8}
                placeholder="Re-enter password"
              />
            </label>

            <button className="auth-btn" type="submit" disabled={loading}>
              {loading ? 'Creating account...' : 'Create Account'}
            </button>
          </form>

          <div className="auth-links">
            <Link to="/login">Already have an account? Sign in</Link>
          </div>
        </div>
      </div>
    </div>
  )
}
