import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function AdminRoute({ children }) {
  const { session, profile, loading } = useAuth()

  if (loading) {
    return <div className="auth-loading">Loading...</div>
  }

  if (!session) {
    return <Navigate to="/login" replace />
  }

  if (profile && profile.role !== 'admin') {
    return <Navigate to="/" replace />
  }

  return children
}
