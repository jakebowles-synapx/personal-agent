import { useState, useEffect } from 'react'
import { useApi } from '../hooks/useApi'

interface Recommendation {
  id: number
  agent_name: string
  title: string
  content: string
  priority: string
  status: string
  created_at: string
  viewed_at: string | null
  acted_at: string | null
  metadata: Record<string, unknown> | null
}

type FilterStatus = 'all' | 'pending' | 'viewed' | 'actioned' | 'dismissed'
type FilterPriority = 'all' | 'urgent' | 'high' | 'normal' | 'low'

export default function Recommendations() {
  const [recommendations, setRecommendations] = useState<Recommendation[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedRec, setSelectedRec] = useState<Recommendation | null>(null)
  const [filterStatus, setFilterStatus] = useState<FilterStatus>('pending')
  const [filterPriority, setFilterPriority] = useState<FilterPriority>('all')
  const { fetchApi } = useApi()

  useEffect(() => {
    loadRecommendations()
  }, [filterStatus, filterPriority])

  const loadRecommendations = async () => {
    setLoading(true)
    const params = new URLSearchParams()
    if (filterStatus !== 'all') params.append('status', filterStatus)
    if (filterPriority !== 'all') params.append('priority', filterPriority)
    params.append('limit', '100')

    const data = await fetchApi<Recommendation[]>(`/api/recommendations?${params}`)
    if (data) {
      setRecommendations(data)
    }
    setLoading(false)
  }

  const updateStatus = async (id: number, action: 'view' | 'action' | 'dismiss') => {
    const endpoint = action === 'view' ? 'view' : action === 'action' ? 'action' : 'dismiss'
    const updated = await fetchApi<Recommendation>(`/api/recommendations/${id}/${endpoint}`, { method: 'POST' })
    if (updated) {
      setRecommendations(prev =>
        prev.map(r => r.id === id ? updated : r)
      )
      if (selectedRec?.id === id) {
        setSelectedRec(updated)
      }
    }
  }

  const deleteRec = async (id: number) => {
    if (!confirm('Delete this recommendation?')) return
    await fetchApi(`/api/recommendations/${id}`, { method: 'DELETE' })
    setRecommendations(prev => prev.filter(r => r.id !== id))
    if (selectedRec?.id === id) {
      setSelectedRec(null)
    }
  }

  const approveKnowledge = async (id: number) => {
    const result = await fetchApi<{ success: boolean; message: string; knowledge_id?: number }>(
      `/api/recommendations/${id}/approve-knowledge`,
      { method: 'POST' }
    )
    if (result?.success) {
      alert(`Knowledge approved: ${result.message}`)
      // Refresh the recommendation to show it's actioned
      await loadRecommendations()
      if (selectedRec?.id === id) {
        const updated = recommendations.find(r => r.id === id)
        if (updated) setSelectedRec({ ...updated, status: 'actioned' })
      }
    } else {
      alert('Failed to approve knowledge')
    }
  }

  const isKnowledgeProposal = (rec: Recommendation) => {
    return rec.metadata?.type === 'knowledge_proposal'
  }

  const formatDate = (isoString: string) => {
    const date = new Date(isoString)
    const today = new Date()
    const yesterday = new Date(today)
    yesterday.setDate(yesterday.getDate() - 1)

    if (date.toDateString() === today.toDateString()) {
      return 'Today at ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
    if (date.toDateString() === yesterday.toDateString()) {
      return 'Yesterday at ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
    return date.toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
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

  const getPriorityLabel = (priority: string) => {
    return priority.charAt(0).toUpperCase() + priority.slice(1)
  }

  const openRec = async (rec: Recommendation) => {
    setSelectedRec(rec)
    if (rec.status === 'pending') {
      await updateStatus(rec.id, 'view')
    }
  }

  return (
    <div className="page-container" style={{ maxWidth: '1200px' }}>
      <div className="page-header">
        <h1 className="page-title">Recommendations</h1>
      </div>

      {/* Filters */}
      <div className="filters">
        <div className="filter-group">
          <label>Status:</label>
          <select value={filterStatus} onChange={e => setFilterStatus(e.target.value as FilterStatus)}>
            <option value="all">All</option>
            <option value="pending">Pending</option>
            <option value="viewed">Viewed</option>
            <option value="actioned">Actioned</option>
            <option value="dismissed">Dismissed</option>
          </select>
        </div>
        <div className="filter-group">
          <label>Priority:</label>
          <select value={filterPriority} onChange={e => setFilterPriority(e.target.value as FilterPriority)}>
            <option value="all">All</option>
            <option value="urgent">Urgent</option>
            <option value="high">High</option>
            <option value="normal">Normal</option>
            <option value="low">Low</option>
          </select>
        </div>
      </div>

      <div className="rec-layout">
        {/* List */}
        <div className="rec-list-panel">
          {loading ? (
            <div className="loading">
              <div className="spinner" />
              <span>Loading...</span>
            </div>
          ) : recommendations.length === 0 ? (
            <div className="empty-state" style={{ padding: '2rem' }}>
              <p>No recommendations found</p>
            </div>
          ) : (
            <div className="rec-list">
              {recommendations.map(rec => (
                <div
                  key={rec.id}
                  className={`rec-list-item ${selectedRec?.id === rec.id ? 'selected' : ''} ${rec.status}`}
                  onClick={() => openRec(rec)}
                >
                  <div className="rec-priority-dot" style={{ backgroundColor: getPriorityColor(rec.priority) }} />
                  <div className="rec-list-content">
                    <div className="rec-list-title">{rec.title}</div>
                    <div className="rec-list-meta">
                      <span className="rec-agent-badge">{rec.agent_name}</span>
                      {isKnowledgeProposal(rec) && <span className="knowledge-badge">Knowledge</span>}
                      <span>{formatDate(rec.created_at)}</span>
                    </div>
                  </div>
                  {rec.status === 'pending' && <div className="unread-dot" />}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Detail */}
        <div className="rec-detail-panel">
          {selectedRec ? (
            <div className="rec-detail">
              <div className="rec-detail-header">
                <div className="rec-detail-priority" style={{ backgroundColor: getPriorityColor(selectedRec.priority) }}>
                  {getPriorityLabel(selectedRec.priority)}
                </div>
                <span className="rec-detail-agent">{selectedRec.agent_name}</span>
                <span className="rec-detail-status">{selectedRec.status}</span>
              </div>
              <h2 className="rec-detail-title">{selectedRec.title}</h2>
              <div className="rec-detail-time">{formatDate(selectedRec.created_at)}</div>
              <div className="rec-detail-content">
                {selectedRec.content.split('\n').map((line, i) => (
                  <p key={i}>{line || '\u00A0'}</p>
                ))}
              </div>
              <div className="rec-detail-actions">
                {isKnowledgeProposal(selectedRec) && selectedRec.status !== 'actioned' && (
                  <button className="btn btn-success" onClick={() => approveKnowledge(selectedRec.id)}>
                    Approve Knowledge
                  </button>
                )}
                {selectedRec.status !== 'actioned' && !isKnowledgeProposal(selectedRec) && (
                  <button className="btn btn-primary" onClick={() => updateStatus(selectedRec.id, 'action')}>
                    Mark as Done
                  </button>
                )}
                {selectedRec.status !== 'dismissed' && (
                  <button className="btn btn-outline" onClick={() => updateStatus(selectedRec.id, 'dismiss')}>
                    Dismiss
                  </button>
                )}
                <button className="btn btn-danger" onClick={() => deleteRec(selectedRec.id)}>
                  Delete
                </button>
              </div>
            </div>
          ) : (
            <div className="empty-state">
              <p>Select a recommendation to view details</p>
            </div>
          )}
        </div>
      </div>

      <style>{`
        .filters {
          display: flex;
          gap: 1rem;
          margin-bottom: 1rem;
        }
        .filter-group {
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }
        .filter-group label {
          font-size: 0.875rem;
          color: var(--text-secondary);
        }
        .filter-group select {
          padding: 0.5rem;
          background-color: var(--bg-secondary);
          border: 1px solid var(--border);
          border-radius: 6px;
          color: var(--text-primary);
          font-size: 0.875rem;
        }
        .rec-layout {
          display: grid;
          grid-template-columns: 400px 1fr;
          gap: 1rem;
          height: calc(100vh - 200px);
          min-height: 400px;
        }
        @media (max-width: 900px) {
          .rec-layout {
            grid-template-columns: 1fr;
          }
          .rec-detail-panel {
            display: ${selectedRec ? 'block' : 'none'};
          }
        }
        .rec-list-panel {
          background-color: var(--bg-secondary);
          border-radius: 8px;
          overflow-y: auto;
        }
        .rec-list {
          padding: 0.5rem;
        }
        .rec-list-item {
          display: flex;
          align-items: flex-start;
          gap: 0.75rem;
          padding: 0.75rem;
          border-radius: 6px;
          cursor: pointer;
          transition: background-color 0.15s;
          position: relative;
        }
        .rec-list-item:hover {
          background-color: var(--bg-tertiary);
        }
        .rec-list-item.selected {
          background-color: var(--bg-tertiary);
        }
        .rec-list-item.viewed, .rec-list-item.actioned, .rec-list-item.dismissed {
          opacity: 0.7;
        }
        .rec-priority-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          margin-top: 6px;
          flex-shrink: 0;
        }
        .rec-list-content {
          flex: 1;
          min-width: 0;
        }
        .rec-list-title {
          font-size: 0.875rem;
          font-weight: 500;
          margin-bottom: 0.25rem;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .rec-list-meta {
          font-size: 0.75rem;
          color: var(--text-secondary);
          display: flex;
          gap: 0.5rem;
          align-items: center;
        }
        .rec-agent-badge {
          background-color: var(--bg-primary);
          padding: 0.125rem 0.5rem;
          border-radius: 4px;
        }
        .unread-dot {
          width: 8px;
          height: 8px;
          background-color: var(--accent);
          border-radius: 50%;
          flex-shrink: 0;
        }
        .rec-detail-panel {
          background-color: var(--bg-secondary);
          border-radius: 8px;
          overflow-y: auto;
        }
        .rec-detail {
          padding: 1.5rem;
        }
        .rec-detail-header {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          margin-bottom: 1rem;
        }
        .rec-detail-priority {
          padding: 0.25rem 0.75rem;
          border-radius: 9999px;
          font-size: 0.75rem;
          font-weight: 500;
          color: white;
        }
        .rec-detail-agent {
          font-size: 0.75rem;
          color: var(--text-secondary);
        }
        .rec-detail-status {
          font-size: 0.75rem;
          color: var(--text-secondary);
          margin-left: auto;
          text-transform: capitalize;
        }
        .rec-detail-title {
          font-size: 1.25rem;
          font-weight: 600;
          margin-bottom: 0.5rem;
        }
        .rec-detail-time {
          font-size: 0.875rem;
          color: var(--text-secondary);
          margin-bottom: 1.5rem;
        }
        .rec-detail-content {
          font-size: 0.9375rem;
          line-height: 1.6;
          margin-bottom: 1.5rem;
        }
        .rec-detail-content p {
          margin-bottom: 0.5rem;
        }
        .rec-detail-actions {
          display: flex;
          gap: 0.75rem;
          flex-wrap: wrap;
        }
        .btn-success {
          background-color: #22c55e;
          color: white;
          border: none;
        }
        .btn-success:hover {
          background-color: #16a34a;
        }
      `}</style>
    </div>
  )
}
