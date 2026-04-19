import { useState } from 'react'
import { Link } from 'react-router-dom'
import { supabase } from '../lib/supabase'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const { error: resetError } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: `${window.location.origin}/reset-password`,
      })

      if (resetError) {
        setError(resetError.message)
        return
      }

      setSent(true)
    } catch {
      setError('Failed to send reset email. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  if (sent) {
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
            <h1 className="auth-title">Check Your Email</h1>
            <p className="auth-subtitle">
              We sent a password reset link to <strong>{email}</strong>. Check your inbox and click the link to reset your password.
            </p>
            <div className="auth-links">
              <Link to="/login">Back to login</Link>
            </div>
          </div>
        </div>
      </div>
    )
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
          <h1 className="auth-title">Reset Password</h1>
          <p className="auth-subtitle">Enter your email and we'll send you a reset link</p>

          <form className="auth-form" onSubmit={handleSubmit}>
            {error && <p className="auth-error">{error}</p>}

            <label className="auth-label">
              Email
              <input
                type="email"
                className="auth-input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                placeholder="you@school.edu"
              />
            </label>

            <button className="auth-btn" type="submit" disabled={loading}>
              {loading ? 'Sending...' : 'Send Reset Link'}
            </button>
          </form>

          <div className="auth-links">
            <Link to="/login">Back to login</Link>
          </div>
        </div>
      </div>
    </div>
  )
}
