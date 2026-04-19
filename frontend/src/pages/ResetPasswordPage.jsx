import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabase'

export default function ResetPasswordPage() {
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    // Supabase handles the recovery token from the URL hash automatically
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (event) => {
        if (event === 'PASSWORD_RECOVERY') {
          // User has a valid recovery session — show the form
        }
      },
    )
    return () => subscription.unsubscribe()
  }, [])

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')

    if (password !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }

    setLoading(true)

    try {
      const { error: updateError } = await supabase.auth.updateUser({
        password,
      })

      if (updateError) {
        setError(updateError.message)
        return
      }

      setSuccess(true)
      setTimeout(() => navigate('/login'), 3000)
    } catch {
      setError('Failed to reset password. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  if (success) {
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
            <h1 className="auth-title">Password Reset!</h1>
            <p className="auth-subtitle">
              Your password has been updated. Redirecting to login...
            </p>
            <div className="auth-links">
              <Link to="/login">Go to login</Link>
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
          <h1 className="auth-title">Set New Password</h1>
          <p className="auth-subtitle">Enter your new password below</p>

          <form className="auth-form" onSubmit={handleSubmit}>
            {error && <p className="auth-error">{error}</p>}

            <label className="auth-label">
              New Password
              <input
                type="password"
                className="auth-input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                placeholder="Min 8 characters"
              />
            </label>

            <label className="auth-label">
              Confirm New Password
              <input
                type="password"
                className="auth-input"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                minLength={8}
                placeholder="Re-enter password"
              />
            </label>

            <button className="auth-btn" type="submit" disabled={loading}>
              {loading ? 'Updating...' : 'Update Password'}
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
