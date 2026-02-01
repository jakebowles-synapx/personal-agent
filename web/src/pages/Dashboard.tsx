import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useApi } from '../hooks/useApi'

interface AgentRun {
  id: number
  agent_name: string
  started_at: string
  completed_at: string | null
  status: string
  summary: string | null
  items_processed: number
}

interface Recommendation {
  id: number
  agent_name: string
  title: string
  content: string
  priority: string
  status: string
  created_at: string
}

interface HealthStatus {
  status: string
  services: {
    orchestrator: boolean
    memory: boolean
    llm: boolean
    microsoft: boolean
    harvest: boolean
    scheduler: boolean
    agents: number
  }
  recommendations: {
    pending: number
  }
}

export default function Dashboard() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [recentRuns, setRecentRuns] = useState<AgentRun[]>([])
  const [pendingRecs, setPendingRecs] = useState<Recommendation[]>([])
  const [loading, setLoading] = useState(true)
  const { fetchApi } = useApi()

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setLoading(true)
    const [healthData, runsData, recsData] = await Promise.all([
      fetchApi<HealthStatus>('/api/health'),
      fetchApi<AgentRun[]>('/api/agents/runs/recent?limit=10'),
      fetchApi<Recommendation[]>('/api/recommendations/pending?limit=5'),
    ])
    if (healthData) setHealth(healthData)
    if (runsData) setRecentRuns(runsData)
    if (recsData) setPendingRecs(recsData)
    setLoading(false)
  }

  const formatTime = (isoString: string) => {
    const date = new Date(isoString)
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  const formatDate = (isoString: string) => {
    const date = new Date(isoString)
    const today = new Date()
    if (date.toDateString() === today.toDateString()) {
      return 'Today ' + formatTime(isoString)
    }
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ' ' + formatTime(isoString)
  }

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'urgent': return '#ef4444'
      case 'high': return '#f59e0b'
      case 'normal': return '#6366f1'
      case 'low': return '#6b7280'
      default: return '#6b7280'
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'var(--success)'
      case 'failed': return 'var(--danger)'
      case 'running': return 'var(--accent)'
      default: return 'var(--text-secondary)'
    }
  }

  if (loading) {
    return (
      <div className="page-container">
        <div className="loading">
          <div className="spinner" />
          <span>Loading dashboard...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Dashboard</h1>
        <button className="btn btn-outline" onClick={loadData}>Refresh</button>
      </div>

      {/* Stats Cards */}
      <div className="dashboard-stats">
        <div className="stat-card">
          <div className="stat-value">{health?.services.agents || 0}</div>
          <div className="stat-label">Active Agents</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{health?.recommendations.pending || 0}</div>
          <div className="stat-label">Pending Items</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: health?.services.scheduler ? 'var(--success)' : 'var(--danger)' }}>
            {health?.services.scheduler ? 'Running' : 'Stopped'}
          </div>
          <div className="stat-label">Scheduler</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: health?.services.microsoft ? 'var(--success)' : 'var(--text-secondary)' }}>
            {health?.services.microsoft ? 'Connected' : 'Not Connected'}
          </div>
          <div className="stat-label">Microsoft 365</div>
        </div>
      </div>

      {/* Pending Recommendations */}
      <div className="dashboard-section">
        <div className="section-header">
          <h2>Pending Recommendations</h2>
          <Link to="/recommendations" className="section-link">View all</Link>
        </div>
        {pendingRecs.length === 0 ? (
          <div className="empty-section">No pending recommendations</div>
        ) : (
          <div className="rec-list">
            {pendingRecs.map(rec => (
              <Link to="/recommendations" key={rec.id} className="rec-item">
                <div className="rec-priority" style={{ backgroundColor: getPriorityColor(rec.priority) }} />
                <div className="rec-content">
                  <div className="rec-title">{rec.title}</div>
                  <div className="rec-meta">
                    <span className="rec-agent">{rec.agent_name}</span>
                    <span className="rec-time">{formatDate(rec.created_at)}</span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Recent Agent Activity */}
      <div className="dashboard-section">
        <div className="section-header">
          <h2>Recent Agent Activity</h2>
          <Link to="/agents" className="section-link">View all</Link>
        </div>
        {recentRuns.length === 0 ? (
          <div className="empty-section">No recent activity</div>
        ) : (
          <div className="activity-list">
            {recentRuns.map(run => (
              <div key={run.id} className="activity-item">
                <div className="activity-status" style={{ backgroundColor: getStatusColor(run.status) }} />
                <div className="activity-content">
                  <div className="activity-agent">{run.agent_name}</div>
                  <div className="activity-summary">{run.summary || run.status}</div>
                </div>
                <div className="activity-time">{formatDate(run.started_at)}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      <style>{`
        .dashboard-stats {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
          gap: 1rem;
          margin-bottom: 2rem;
        }
        .stat-card {
          background-color: var(--bg-secondary);
          padding: 1.5rem;
          border-radius: 8px;
          text-align: center;
        }
        .stat-value {
          font-size: 1.5rem;
          font-weight: 600;
          margin-bottom: 0.25rem;
        }
        .stat-label {
          font-size: 0.75rem;
          color: var(--text-secondary);
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }
        .dashboard-section {
          background-color: var(--bg-secondary);
          border-radius: 8px;
          padding: 1.5rem;
          margin-bottom: 1rem;
        }
        .section-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 1rem;
        }
        .section-header h2 {
          font-size: 1rem;
          font-weight: 600;
        }
        .section-link {
          font-size: 0.875rem;
          color: var(--accent);
          text-decoration: none;
        }
        .section-link:hover {
          text-decoration: underline;
        }
        .empty-section {
          color: var(--text-secondary);
          font-size: 0.875rem;
          padding: 1rem 0;
        }
        .rec-list {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }
        .rec-item {
          display: flex;
          align-items: flex-start;
          gap: 0.75rem;
          padding: 0.75rem;
          background-color: var(--bg-tertiary);
          border-radius: 6px;
          text-decoration: none;
          color: inherit;
          transition: background-color 0.15s;
        }
        .rec-item:hover {
          background-color: var(--border);
        }
        .rec-priority {
          width: 4px;
          height: 100%;
          min-height: 40px;
          border-radius: 2px;
        }
        .rec-content {
          flex: 1;
          min-width: 0;
        }
        .rec-title {
          font-size: 0.875rem;
          font-weight: 500;
          margin-bottom: 0.25rem;
        }
        .rec-meta {
          font-size: 0.75rem;
          color: var(--text-secondary);
          display: flex;
          gap: 0.75rem;
        }
        .activity-list {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }
        .activity-item {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          padding: 0.5rem;
        }
        .activity-status {
          width: 8px;
          height: 8px;
          border-radius: 50%;
        }
        .activity-content {
          flex: 1;
          min-width: 0;
        }
        .activity-agent {
          font-size: 0.875rem;
          font-weight: 500;
        }
        .activity-summary {
          font-size: 0.75rem;
          color: var(--text-secondary);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .activity-time {
          font-size: 0.75rem;
          color: var(--text-secondary);
          white-space: nowrap;
        }
      `}</style>
    </div>
  )
}
