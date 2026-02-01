import { useState, useEffect } from 'react'
import { useApi } from '../hooks/useApi'

interface AgentStatus {
  name: string
  description: string
  last_run: {
    id: number
    agent_name: string
    started_at: string
    completed_at: string | null
    status: string
    summary: string | null
    items_processed: number
  } | null
  next_run: string | null
  is_scheduled: boolean
}

interface AgentRun {
  id: number
  agent_name: string
  started_at: string
  completed_at: string | null
  status: string
  summary: string | null
  items_processed: number
  error_message: string | null
}

export default function Agents() {
  const [agents, setAgents] = useState<AgentStatus[]>([])
  const [selectedAgent, setSelectedAgent] = useState<AgentStatus | null>(null)
  const [runs, setRuns] = useState<AgentRun[]>([])
  const [loading, setLoading] = useState(true)
  const [triggering, setTriggering] = useState<string | null>(null)
  const { fetchApi } = useApi()

  useEffect(() => {
    loadAgents()
  }, [])

  useEffect(() => {
    if (selectedAgent) {
      loadRuns(selectedAgent.name)
    }
  }, [selectedAgent])

  const loadAgents = async () => {
    setLoading(true)
    const data = await fetchApi<AgentStatus[]>('/api/agents')
    if (data) {
      setAgents(data)
      if (!selectedAgent && data.length > 0) {
        setSelectedAgent(data[0])
      }
    }
    setLoading(false)
  }

  const loadRuns = async (agentName: string) => {
    const data = await fetchApi<AgentRun[]>(`/api/agents/${agentName}/runs?limit=20`)
    if (data) {
      setRuns(data)
    }
  }

  const triggerAgent = async (agentName: string) => {
    setTriggering(agentName)
    const result = await fetchApi<{ success: boolean; error?: string }>(
      `/api/agents/${agentName}/trigger`,
      { method: 'POST' }
    )

    if (result?.success) {
      // Reload agent status and runs
      await loadAgents()
      if (selectedAgent?.name === agentName) {
        await loadRuns(agentName)
      }
    } else if (result?.error) {
      alert(`Failed to trigger agent: ${result.error}`)
    }

    setTriggering(null)
  }

  const formatDateTime = (isoString: string | null) => {
    if (!isoString) return 'Never'
    const date = new Date(isoString)
    const now = new Date()
    const diffMs = date.getTime() - now.getTime()
    const diffMins = Math.round(diffMs / 60000)

    if (diffMins > 0 && diffMins < 60) {
      return `in ${diffMins} min`
    }
    if (diffMins >= 60 && diffMins < 1440) {
      return `in ${Math.round(diffMins / 60)} hours`
    }

    return date.toLocaleString([], {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'var(--success)'
      case 'failed': return 'var(--danger)'
      case 'running': return 'var(--accent)'
      default: return 'var(--text-secondary)'
    }
  }

  const getAgentIcon = (name: string) => {
    switch (name) {
      case 'chat': return '💬'
      case 'briefing': return '📋'
      case 'action_item': return '✅'
      case 'memory': return '🧠'
      case 'anomaly': return '⚠️'
      default: return '🤖'
    }
  }

  if (loading) {
    return (
      <div className="page-container">
        <div className="loading">
          <div className="spinner" />
          <span>Loading agents...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="page-container" style={{ maxWidth: '1200px' }}>
      <div className="page-header">
        <h1 className="page-title">Agents</h1>
        <button className="btn btn-outline" onClick={loadAgents}>Refresh</button>
      </div>

      <div className="agents-layout">
        {/* Agent Cards */}
        <div className="agents-grid">
          {agents.map(agent => (
            <div
              key={agent.name}
              className={`agent-card ${selectedAgent?.name === agent.name ? 'selected' : ''}`}
              onClick={() => setSelectedAgent(agent)}
            >
              <div className="agent-card-header">
                <span className="agent-icon">{getAgentIcon(agent.name)}</span>
                <h3 className="agent-name">{agent.name}</h3>
                {agent.is_scheduled && (
                  <span className="scheduled-badge" title="Runs on schedule">
                    🕐
                  </span>
                )}
              </div>
              <p className="agent-description">{agent.description}</p>
              <div className="agent-card-footer">
                {agent.last_run ? (
                  <div className="last-run">
                    <span
                      className="status-dot"
                      style={{ backgroundColor: getStatusColor(agent.last_run.status) }}
                    />
                    <span>
                      {agent.last_run.status === 'completed' ? agent.last_run.summary || 'Completed' : agent.last_run.status}
                    </span>
                  </div>
                ) : (
                  <span className="no-runs">No runs yet</span>
                )}
                {agent.is_scheduled && agent.next_run && (
                  <div className="next-run">
                    Next: {formatDateTime(agent.next_run)}
                  </div>
                )}
              </div>
              <button
                className="btn btn-primary trigger-btn"
                onClick={(e) => {
                  e.stopPropagation()
                  triggerAgent(agent.name)
                }}
                disabled={triggering === agent.name}
              >
                {triggering === agent.name ? 'Running...' : 'Run Now'}
              </button>
            </div>
          ))}
        </div>

        {/* Run History */}
        {selectedAgent && (
          <div className="runs-panel">
            <h2>
              {getAgentIcon(selectedAgent.name)} {selectedAgent.name} - Run History
            </h2>
            {runs.length === 0 ? (
              <div className="empty-state" style={{ padding: '2rem' }}>
                No runs recorded yet
              </div>
            ) : (
              <div className="runs-list">
                {runs.map(run => (
                  <div key={run.id} className="run-item">
                    <div className="run-status">
                      <span
                        className="status-indicator"
                        style={{ backgroundColor: getStatusColor(run.status) }}
                      />
                      <span className="status-text">{run.status}</span>
                    </div>
                    <div className="run-details">
                      <div className="run-summary">
                        {run.summary || (run.error_message ? `Error: ${run.error_message}` : 'No summary')}
                      </div>
                      <div className="run-meta">
                        <span>{formatDateTime(run.started_at)}</span>
                        {run.items_processed > 0 && (
                          <span>{run.items_processed} items processed</span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <style>{`
        .agents-layout {
          display: flex;
          flex-direction: column;
          gap: 1.5rem;
        }
        .agents-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
          gap: 1rem;
        }
        .agent-card {
          background-color: var(--bg-secondary);
          border: 1px solid var(--border);
          border-radius: 12px;
          padding: 1.25rem;
          cursor: pointer;
          transition: all 0.15s;
        }
        .agent-card:hover {
          border-color: var(--accent);
        }
        .agent-card.selected {
          border-color: var(--accent);
          box-shadow: 0 0 0 1px var(--accent);
        }
        .agent-card-header {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          margin-bottom: 0.5rem;
        }
        .agent-icon {
          font-size: 1.5rem;
        }
        .agent-name {
          font-size: 1rem;
          font-weight: 600;
          flex: 1;
        }
        .scheduled-badge {
          font-size: 1rem;
        }
        .agent-description {
          font-size: 0.875rem;
          color: var(--text-secondary);
          margin-bottom: 1rem;
          line-height: 1.4;
        }
        .agent-card-footer {
          font-size: 0.75rem;
          color: var(--text-secondary);
          margin-bottom: 1rem;
        }
        .last-run {
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }
        .status-dot {
          width: 6px;
          height: 6px;
          border-radius: 50%;
        }
        .next-run {
          margin-top: 0.25rem;
        }
        .no-runs {
          font-style: italic;
        }
        .trigger-btn {
          width: 100%;
        }
        .runs-panel {
          background-color: var(--bg-secondary);
          border-radius: 12px;
          padding: 1.5rem;
        }
        .runs-panel h2 {
          font-size: 1rem;
          margin-bottom: 1rem;
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }
        .runs-list {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }
        .run-item {
          display: flex;
          gap: 1rem;
          padding: 0.75rem;
          background-color: var(--bg-tertiary);
          border-radius: 8px;
        }
        .run-status {
          display: flex;
          align-items: flex-start;
          gap: 0.5rem;
          min-width: 90px;
        }
        .status-indicator {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          margin-top: 5px;
        }
        .status-text {
          font-size: 0.75rem;
          font-weight: 500;
          text-transform: capitalize;
        }
        .run-details {
          flex: 1;
          min-width: 0;
        }
        .run-summary {
          font-size: 0.875rem;
          margin-bottom: 0.25rem;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .run-meta {
          font-size: 0.75rem;
          color: var(--text-secondary);
          display: flex;
          gap: 1rem;
        }
      `}</style>
    </div>
  )
}
