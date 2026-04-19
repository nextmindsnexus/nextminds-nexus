import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { supabase } from '../lib/supabase'

export default function ProfileDropdown() {
  const { user, profile, isAdmin, signOut } = useAuth()
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    function handleClickOutside(e) {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  if (!user) return null

  const initials = profile
    ? `${(profile.first_name || '')[0] || ''}${(profile.last_name || '')[0] || ''}`.toUpperCase() || '?'
    : (user.email?.[0] || '?').toUpperCase()

  const displayName = profile
    ? `${profile.first_name || ''} ${profile.last_name || ''}`.trim() || user.email
    : user.email

  async function handleResetPassword() {
    try {
      await supabase.auth.resetPasswordForEmail(user.email, {
        redirectTo: `${window.location.origin}/reset-password`,
      })
      alert('Password reset email sent. Check your inbox.')
    } catch {
      alert('Failed to send reset email.')
    }
    setOpen(false)
  }

  return (
    <div className="profile-dropdown" ref={ref}>
      <button
        className="profile-avatar"
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-label="Profile menu"
      >
        {initials}
      </button>

      {open && (
        <div className="profile-menu">
          <div className="profile-info">
            <strong>{displayName}</strong>
            <small>{user.email}</small>
            {profile?.role && <span className="profile-role">{profile.role}</span>}
          </div>
          <hr />
          <button type="button" onClick={handleResetPassword}>
            Change Password
          </button>
          {isAdmin && (
            <button type="button" onClick={() => { navigate('/admin'); setOpen(false) }}>
              Admin Dashboard
            </button>
          )}
          <hr />
          <button type="button" onClick={() => { signOut(); setOpen(false) }}>
            Log Out
          </button>
        </div>
      )}
    </div>
  )
}
