import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import ProfileDropdown from '../components/ProfileDropdown'
import { apiFetch } from '../utils/api'

const TABS = ['users', 'content', 'stats', 'health']

export default function AdminPage() {
  const [tab, setTab] = useState('users')
  const navigate = useNavigate()

  return (
    <div className="admin-page">
      <header className="admin-header">
        <div className="admin-header-left">
          <h1>Admin Dashboard</h1>
          <button className="admin-back-btn" type="button" onClick={() => navigate('/')}>
            Back to Chat
          </button>
        </div>
        <ProfileDropdown />
      </header>

      <nav className="admin-tabs">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            className={`admin-tab ${tab === t ? 'active' : ''}`}
            onClick={() => setTab(t)}
          >
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </nav>

      <div className="admin-content">
        {tab === 'users' && <UsersTab />}
        {tab === 'content' && <ContentTab />}
        {tab === 'stats' && <StatsTab />}
        {tab === 'health' && <HealthTab />}
      </div>
    </div>
  )
}

/* ---- Users Tab ---- */
function UsersTab() {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showCreate, setShowCreate] = useState(false)

  const loadUsers = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await apiFetch('/api/admin/users')
      if (!res.ok) throw new Error('Failed to load users')
      const data = await res.json()
      setUsers(data.users || [])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadUsers() }, [loadUsers])

  async function toggleActive(user) {
    try {
      const res = await apiFetch(`/api/admin/users/${user.id}`, {
        method: 'PUT',
        body: JSON.stringify({ is_active: !user.is_active }),
      })
      if (!res.ok) throw new Error('Failed to update user')
      loadUsers()
    } catch (e) {
      setError(e.message)
    }
  }

  async function changeRole(user, newRole) {
    try {
      const res = await apiFetch(`/api/admin/users/${user.id}`, {
        method: 'PUT',
        body: JSON.stringify({ role: newRole }),
      })
      if (!res.ok) throw new Error('Failed to update role')
      loadUsers()
    } catch (e) {
      setError(e.message)
    }
  }

  async function deleteUser(user) {
    if (!confirm(`Delete user ${user.email}? This cannot be undone.`)) return
    try {
      const res = await apiFetch(`/api/admin/users/${user.id}`, { method: 'DELETE' })
      if (!res.ok) throw new Error('Failed to delete user')
      loadUsers()
    } catch (e) {
      setError(e.message)
    }
  }

  if (loading) return <p className="admin-loading">Loading users...</p>
  if (error) return <p className="admin-error">{error}</p>

  return (
    <div>
      <div className="admin-section-header">
        <h2>User Management</h2>
        <button type="button" className="admin-btn" onClick={() => setShowCreate(true)}>
          Create User
        </button>
      </div>

      {showCreate && <CreateUserForm onDone={() => { setShowCreate(false); loadUsers() }} onCancel={() => setShowCreate(false)} />}

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Name</th>
              <th>Role</th>
              <th>Active</th>
              <th>Chats</th>
              <th>Searches</th>
              <th>Last Active</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.email}</td>
                <td>{u.first_name} {u.last_name}</td>
                <td>
                  <select value={u.role} onChange={(e) => changeRole(u, e.target.value)}>
                    <option value="user">user</option>
                    <option value="teacher">teacher</option>
                    <option value="admin">admin</option>
                  </select>
                </td>
                <td>
                  <button type="button" className={`admin-badge ${u.is_active ? 'active' : 'inactive'}`} onClick={() => toggleActive(u)}>
                    {u.is_active ? 'Active' : 'Inactive'}
                  </button>
                </td>
                <td>{u.chat_count ?? 0}</td>
                <td>{u.search_count ?? 0}</td>
                <td>{u.last_active || '—'}</td>
                <td>
                  <button type="button" className="admin-btn-danger" onClick={() => deleteUser(u)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/* ---- Create User Form ---- */
function CreateUserForm({ onDone, onCancel }) {
  const [form, setForm] = useState({ email: '', password: '', first_name: '', last_name: '', role: 'user' })
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      const res = await apiFetch('/api/admin/users', {
        method: 'POST',
        body: JSON.stringify(form),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || 'Failed to create user')
      }
      onDone()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="admin-create-form" onSubmit={handleSubmit}>
      <h3>Create New User</h3>
      {error && <p className="admin-error">{error}</p>}
      <div className="admin-form-row">
        <input placeholder="Email" type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <input placeholder="Password" type="password" required minLength={6} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
      </div>
      <div className="admin-form-row">
        <input placeholder="First Name" required value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} />
        <input placeholder="Last Name" required value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} />
      </div>
      <div className="admin-form-row">
        <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
          <option value="user">user</option>
          <option value="teacher">teacher</option>
          <option value="admin">admin</option>
        </select>
        <button type="submit" className="admin-btn" disabled={submitting}>{submitting ? 'Creating...' : 'Create'}</button>
        <button type="button" className="admin-btn-secondary" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  )
}

/* ---- Content Tab ---- */
function ContentTab() {
  const [ingesting, setIngesting] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  async function triggerIngest() {
    setIngesting(true)
    setError('')
    setResult(null)
    try {
      const res = await apiFetch('/api/admin/ingest', { method: 'POST' })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Ingestion failed')
      setResult({ type: 'ingest', ...data })
    } catch (e) {
      setError(e.message)
    } finally {
      setIngesting(false)
    }
  }

  return (
    <div>
      <h2>Content Management</h2>
      <p style={{ maxWidth: '600px', marginBottom: '1.5rem', color: '#555', lineHeight: '1.5' }}>
        Keep your learning resources up to date. Clicking the button below will automatically gather the latest activities.
      </p>
      <div className="admin-actions-row">
        <button type="button" className="admin-btn" onClick={triggerIngest} disabled={ingesting}>
          {ingesting ? 'Processing...' : 'Run Re-crawl'}
        </button>
      </div>
      {error && <p className="admin-error">{error}</p>}
      {result && (
        <div className="admin-result-card">
          <div className="admin-result-header">
            <h3>Processing Complete</h3>
            <span className={`admin-result-status ${result.status === 'completed' ? 'success' : 'warning'}`}>
              {result.status || 'unknown'}
            </span>
          </div>

          <div className="admin-result-grid">
            <ResultItem label="Total Crawled" value={result.total_crawled} />
            <ResultItem label="Added" value={result.added} />
            <ResultItem label="Updated" value={result.updated} />
            <ResultItem label="Removed" value={result.removed} />
            <ResultItem label="Errors" value={result.errors} />
          </div>
        </div>
      )}
    </div>
  )
}

function ResultItem({ label, value }) {
  return (
    <div className="admin-result-item">
      <span className="admin-result-label">{label}</span>
      <span className="admin-result-value">{value ?? 0}</span>
    </div>
  )
}

/* ---- Stats Tab ---- */
function StatsTab() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    (async () => {
      try {
        const res = await apiFetch('/api/admin/stats')
        if (!res.ok) throw new Error('Failed to load stats')
        setStats(await res.json())
      } catch (e) {
        setError(e.message)
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  if (loading) return <p className="admin-loading">Loading stats...</p>
  if (error) return <p className="admin-error">{error}</p>
  if (!stats) return null

  return (
    <div>
      <h2>Catalog Statistics</h2>
      <div className="admin-stats-grid">
        <div className="admin-stat-card">
          <span className="stat-value">{stats.total}</span>
          <span className="stat-label">Total Activities</span>
        </div>
        <div className="admin-stat-card">
          <span className="stat-value">{stats.active}</span>
          <span className="stat-label">Active</span>
        </div>
        <div className="admin-stat-card">
          <span className="stat-value">{stats.grade_bands}</span>
          <span className="stat-label">Grade Bands</span>
        </div>
        <div className="admin-stat-card">
          <span className="stat-value">{stats.stages}</span>
          <span className="stat-label">Stages</span>
        </div>
      </div>
      {stats.by_grade_band && Object.keys(stats.by_grade_band).length > 0 && (
        <div className="admin-breakdown">
          <h3>By Grade Band</h3>
          <ul>{Object.entries(stats.by_grade_band).map(([k, v]) => <li key={k}><strong>{k}:</strong> {v}</li>)}</ul>
        </div>
      )}
      {stats.by_stage && Object.keys(stats.by_stage).length > 0 && (
        <div className="admin-breakdown">
          <h3>By Stage</h3>
          <ul>{Object.entries(stats.by_stage).map(([k, v]) => <li key={k}><strong>{k}:</strong> {v}</li>)}</ul>
        </div>
      )}
    </div>
  )
}

/* ---- Health Tab ---- */
function HealthTab() {
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    (async () => {
      try {
        const res = await apiFetch('/api/admin/health')
        setHealth(await res.json())
      } catch {
        setHealth({ status: 'error', database: 'unknown', embedding_model: 'unknown' })
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  if (loading) return <p className="admin-loading">Checking health...</p>
  if (!health) return null

  return (
    <div>
      <h2>System Health</h2>
      <div className="admin-stats-grid">
        <div className={`admin-stat-card ${health.status === 'healthy' ? 'healthy' : 'unhealthy'}`}>
          <span className="stat-value">{health.status}</span>
          <span className="stat-label">Overall</span>
        </div>
        <div className={`admin-stat-card ${health.database === 'connected' ? 'healthy' : 'unhealthy'}`}>
          <span className="stat-value">{health.database}</span>
          <span className="stat-label">Database</span>
        </div>
        <div className={`admin-stat-card ${health.embedding_model === 'loaded' ? 'healthy' : 'unhealthy'}`}>
          <span className="stat-value">{health.embedding_model}</span>
          <span className="stat-label">Embedding Model</span>
        </div>
      </div>
    </div>
  )
}
